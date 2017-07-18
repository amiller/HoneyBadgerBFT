import unittest
import gevent
import random
from gevent.event import Event
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.core.binaryagreement import binaryagreement
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.util.router import broadcast_router
from collections import defaultdict

def dummy_coin(sid, N, f):
    counter = defaultdict(int)
    events = defaultdict(Event)
    def getCoin(round):
        # Return a pseudorandom number depending on the round, without blocking
        counter[round] += 1
        if counter[round] == f+1: events[round].set()
        events[round].wait()
        return hash((sid,round)) % 2
    return getCoin

### Test binary agreement with a dummy coin
def _test_binaryagreement_dummy(N=4, f=1, seed=None):
    # Generate keys
    sid = 'sidA'
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = broadcast_router(N, seed=seed)

    threads = []
    inputs = []
    outputs = []
    coin = dummy_coin(sid, N, f)  # One dummy coin function for all nodes

    for i in range(N):
        inputs.append(Queue())
        outputs.append(Queue())

        t = gevent.spawn(binaryagreement, sid, i, N, f, coin,
                         inputs[i].get, outputs[i].put_nowait, sends[i], recvs[i])
        threads.append(t)

    for i in range(N):
        inputs[i].put(random.randint(0,1))
    #gevent.killall(threads[N-f:])
    #gevent.sleep(3)
    #for i in range(N-f, N):
    #    inputs[i].put(0)
    try:
        outs = [outputs[i].get() for i in range(N)]
        assert len(set(outs)) == 1
        try: gevent.joinall(threads)
        except gevent.hub.LoopExit: pass
    except KeyboardInterrupt:
        gevent.killall(threads)
        raise

def test_binaryagreement_dummy():
    _test_binaryagreement_dummy()

### Test binary agreement with boldyreva coin
def _make_coins(sid, N, f, seed):
    # Generate keys
    PK, SKs = dealer(N, f+1)
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = broadcast_router(N, seed=seed)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]
    return coins

def _test_binaryagreement(N=4, f=1, seed=None):
    # Generate keys
    sid = 'sidA'
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    rnd = random.Random(seed)

    # Instantiate the common coin
    coins_seed = rnd.random()
    coins = _make_coins(sid+'COIN', N, f, coins_seed)

    # Router
    router_seed = rnd.random()
    sends, recvs = broadcast_router(N, seed=seed)

    threads = []
    inputs = []
    outputs = []

    for i in range(N):
        inputs.append(Queue())
        outputs.append(Queue())

        t = gevent.spawn(binaryagreement, sid, i, N, f, coins[i],
                         inputs[i].get, outputs[i].put_nowait, sends[i], recvs[i])
        threads.append(t)

    for i in range(N):
        inputs[i].put(random.randint(0,1))
    #gevent.killall(threads[N-f:])
    #gevent.sleep(3)
    #for i in range(N-f, N):
    #    inputs[i].put(0)
    try:
        outs = [outputs[i].get() for i in range(N)]
        assert len(set(outs)) == 1
        try: gevent.joinall(threads)
        except gevent.hub.LoopExit: pass
    except KeyboardInterrupt:
        gevent.killall(threads)
        raise

def test_binaryagreement():
    for i in range(5): _test_binaryagreement(seed=i)
