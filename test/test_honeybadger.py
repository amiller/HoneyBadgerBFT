import unittest
import gevent
import random
import ast
from gevent.event import Event
from gevent.queue import Queue
import honeybadgerbft.core.honeybadger
reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.util.router import simple_router
from collections import defaultdict

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
                                    input_queues[i].get, output_queues[i].put,
                                    encode=repr, decode=ast.literal_eval,
                                    max_rounds=3)
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
