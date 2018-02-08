import random
from collections import defaultdict

import gevent
from gevent.event import Event
from gevent.queue import Queue
from pytest import fixture, mark, raises

import honeybadgerbft.core.honeybadger
reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import BroadcastTag


@fixture
def recv_queues(request):
    from honeybadgerbft.core.honeybadger import BroadcastReceiverQueues
    number_of_nodes = getattr(request, 'N', 4)
    queues = {
        tag.value: [Queue() for _ in range(number_of_nodes)]
        for tag in BroadcastTag if tag != BroadcastTag.TPKE
    }
    queues[BroadcastTag.TPKE.value] = Queue()
    return BroadcastReceiverQueues(**queues)


def simple_router(N, maxdelay=0.005, seed=None):
    """Builds a set of connected channels, with random delay

    :return: (receives, sends)
    """
    rnd = random.Random(seed)
    #if seed is not None: print 'ROUTER SEED: %f' % (seed,)

    queues = [Queue() for _ in range(N)]
    _threads = []

    def makeSend(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
            if not i%3:
                delay *= 1000
            #delay = 0.1
            #print 'SEND   %8s [%2d -> %2d] %2.1f' % (o[0], i, j, delay*1000), o[1:]
            gevent.spawn_later(delay, queues[j].put_nowait, (i,o))
        return _send

    def makeRecv(j):
        def _recv():
            (i,o) = queues[j].get()
            #print 'RECV %8s [%2d -> %2d]' % (o[0], i, j)
            return (i,o)
        return _recv

    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])


### Test asynchronous common subset
def _test_honeybadger(N=4, f=1, seed=None):
    sid = 'sidA'
    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)
    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    rnd = random.Random(seed)
    #print 'SEED:', seed
    router_seed = rnd.random()
    sends, recvs = simple_router(N, seed=router_seed)

    badgers = [None] * N
    threads = [None] * N
    for i in range(N):
        badgers[i] = HoneyBadgerBFT(sid, i, 1, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    sends[i], recvs[i])
        threads[i] = gevent.spawn(badgers[i].run)

    for i in range(N):
        #if i == 1: continue
        badgers[i].submit_tx('<[HBBFT Input %d]>' % i)

    for i in range(N):
        badgers[i].submit_tx('<[HBBFT Input %d]>' % (i+10))

    for i in range(N):
        badgers[i].submit_tx('<[HBBFT Input %d]>' % (i+20))

    #gevent.killall(threads[N-f:])
    #gevent.sleep(3)
    #for i in range(N-f, N):
    #    inputs[i].put(0)
    try:
        outs = [threads[i].get() for i in range(N)]

        # Consistency check
        assert len(set(outs)) == 1

    except KeyboardInterrupt:
        gevent.killall(threads)
        raise


def test_honeybadger():
    _test_honeybadger()


@mark.parametrize('message', ('broadcast message',))
@mark.parametrize('node_id', range(4))
@mark.parametrize('tag', [e.value for e in BroadcastTag])
@mark.parametrize('sender', range(4))
def test_broadcast_receiver_loop(sender, tag, node_id, message, recv_queues):
    from honeybadgerbft.core.honeybadger import broadcast_receiver_loop
    recv = Queue()
    recv.put((sender, (tag, node_id, message)))
    gevent.spawn(broadcast_receiver_loop, recv.get, recv_queues)
    recv_queue = getattr(recv_queues, tag)
    if tag != BroadcastTag.TPKE.value:
        recv_queue = recv_queue[node_id]
    assert recv_queue,get() == (sender, message)


@mark.parametrize('message', ('broadcast message',))
@mark.parametrize('node_id', range(4))
@mark.parametrize('tag', ('BogusTag', None, 123))
@mark.parametrize('sender', range(4))
def test_broadcast_receiver_loop_raises(sender, tag, node_id, message, recv_queues):
    from honeybadgerbft.core.honeybadger import broadcast_receiver_loop
    from honeybadgerbft.exceptions import UnknownTagError
    recv = Queue()
    recv.put((sender, (tag, node_id, message)))
    with raises(UnknownTagError) as exc:
        broadcast_receiver_loop(recv.get, recv_queues)
    expected_err_msg = 'Unknown tag: {}! Must be one of {}.'.format(
        tag, BroadcastTag.__members__.keys())
    assert exc.value.message == expected_err_msg
    recv_queues_dict = recv_queues._asdict()
    tpke_queue = recv_queues_dict.pop(BroadcastTag.TPKE.value)
    assert tpke_queue.empty()
    assert all([q.empty() for queues in recv_queues_dict.values() for q in queues])
