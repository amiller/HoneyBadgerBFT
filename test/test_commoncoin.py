import unittest
import gevent
import random
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.crypto.threshsig.boldyreva import dealer

def simple_router(N, maxdelay=0.01, seed=None):
    """Builds a set of connected channels, with random delay
    @return (receives, sends)
    """
    rnd = random.Random(seed)
    #if seed is not None: print 'ROUTER SEED: %f' % (seed,)
    
    queues = [Queue() for _ in range(N)]

    def makeBroadcast(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
            #print 'BC   %8s [%2d -> %2d] %2.1f' % (o[0], i, j, delay*1000)
            gevent.spawn_later(delay, queues[j].put, (i,o))
            #queues[j].put((i, o))
        def _bc(o):
            for j in range(N): _send(j, o)
        return _bc

    def makeRecv(j):
        def _recv():
            (i,o) = queues[j].get()
            #print 'RECV %8s [%2d -> %2d]' % (o[0], i, j)
            return (i,o)
        return _recv

    return ([makeBroadcast(i) for i in range(N)],
            [makeRecv(j)      for j in range(N)])


def byzantine_router(N, maxdelay=0.01, seed=None, **byzargs):
    """Builds a set of connected channels, with random delay.

    :return: (receives, sends) endpoints.
    """
    rnd = random.Random(seed)
    #if seed is not None: print 'ROUTER SEED: %f' % (seed,)

    queues = [Queue() for _ in range(N)]

    def makeBroadcast(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
            gevent.spawn_later(delay, queues[j].put, (i,o))
        def _bc(o):
            for j in range(N): _send(j, o)
        return _bc

    def makeRecv(j):
        def _recv():
            return queues[j].get()

        def _recv_redundant():
            i, o = queues[j].get()
            if i == 3 and o[1] == 3:
                o = list(o)
                o[1] -= 1
                o = tuple(o)
            return (i,o)

        def _recv_fail_pk_verify_share():
            (i,o) = queues[j].get()
            if i == 3 and o[1] == 3:
                o = list(o)
                o[1] += 1
                o = tuple(o)
            return (i,o)

        if j == byzargs.get('node') and byzargs.get('sig_redundant'):
            return _recv_redundant
        if j == byzargs.get('node') and byzargs.get('sig_err'):
            return _recv_fail_pk_verify_share
        return _recv
        
    return ([makeBroadcast(i) for i in range(N)],
            [makeRecv(j)      for j in range(N)])


### Test
def _test_commoncoin(N=4, f=1, seed=None):
    # Generate keys
    PK, SKs = dealer(N, f+1)
    sid = 'sidA'
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = simple_router(N, seed=seed)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]

    for i in range(10):
        threads = [gevent.spawn(c, i) for c in coins]
        gevent.joinall(threads)
        assert len(set([t.value for t in threads])) == 1
    return True


def test_commoncoin():
    _test_commoncoin()


def test_when_signature_share_verify_fails():
    N = 4
    f = 1
    seed = None
    PK, SKs = dealer(N, f+1)
    sid = 'sidA'
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = byzantine_router(N, seed=seed, node=2, sig_err=True)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]
    for i in range(10):
        threads = [gevent.spawn(c, i) for c in coins]
        gevent.joinall(threads)
        assert len(set([t.value for t in threads])) == 1


def test_when_redundant_signature_share_is_received():
    N = 4
    f = 1
    seed = None
    PK, SKs = dealer(N, f+1)
    sid = 'sidA'
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = byzantine_router(N, seed=seed, node=2, sig_redundant=True)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]
    for i in range(10):
        threads = [gevent.spawn(c, i) for c in coins]
        gevent.joinall(threads)
        assert len(set([t.value for t in threads])) == 1
