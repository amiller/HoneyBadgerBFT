import unittest
import gevent
import random
from gevent.event import Event
from gevent.queue import Queue
import honeybadgerbft.core.honeybadger
reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from collections import defaultdict

def simple_router(N, maxdelay=0.005, seed=None):
    """Builds a set of connected channels, with random delay
    @return (receives, sends)
    """
    rnd = random.Random(seed)
    #if seed is not None: print 'ROUTER SEED: %f' % (seed,)
    
    queues = [Queue() for _ in range(N)]
    _threads = []

    def makeSend(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
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

    B = N # 1 tx per node, per round

    badgers = [None] * N
    threads = [None] * N
    input_queues = [Queue() for _ in range(N)]  # to submit lists of txes
    output_queues = [Queue() for _ in range(N)] # to read lists of txes

    for i in range(N):
        input_queues[i].put(['<[HBBFT Input %d]>' % i])

    for i in range(N):
        badgers[i] = HoneyBadgerBFT(sid, i, B, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    sends[i], recvs[i],
                                    input_queues[i].get, output_queues[i].put, 3)
        threads[i] = gevent.spawn(badgers[i].run)

    for i in range(N):
        input_queues[i].put(['<[HBBFT Input %d]>' % (i+10)])

    for i in range(N):
        input_queues[i].put(['<[HBBFT Input %d]>' % (i+20)])
        
    try:
        # Wait for each badger to finish running
        for i in range(N):
            threads[i].get()
            output_queues[i].put(StopIteration)

        outs = [tuple(output_queues[i]) for i in range(N)]

        # Consistency check
        assert len(set(outs)) == 1
        
    except KeyboardInterrupt:
        gevent.killall(threads)
        raise

from nose2.tools import params

def test_honeybadger():
    _test_honeybadger()

