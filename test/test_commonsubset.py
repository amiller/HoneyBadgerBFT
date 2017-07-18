import unittest
import gevent
import random
from gevent.event import Event
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.core.binaryagreement import binaryagreement
from honeybadgerbft.core.reliablebroadcast import reliablebroadcast
from honeybadgerbft.core.commonsubset import commonsubset
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.util.router import simple_router
from collections import defaultdict

### Make the threshold signature common coins
def _make_commonsubset(sid, pid, N, f, PK, SK, input, send, recv):

    def broadcast(o):
        for j in range(N): send(j, o)

    coin_recvs = [None] * N
    aba_recvs  = [None] * N
    rbc_recvs  = [None] * N

    aba_inputs  = [Queue(1) for _ in range(N)]
    aba_outputs = [Queue(1) for _ in range(N)]
    rbc_outputs = [Queue(1) for _ in range(N)]

    def _setup(j):
        def coin_bcast(o):
            broadcast(('ACS_COIN', j, o))

        coin_recvs[j] = Queue()
        coin = shared_coin(sid + 'COIN' + str(j), pid, N, f, PK, SK,
                           coin_bcast, coin_recvs[j].get)

        def aba_bcast(o):
            broadcast(('ACS_ABA', j, o))

        aba_recvs[j] = Queue()
        aba = gevent.spawn(binaryagreement, sid+'ABA'+str(j), pid, N, f, coin,
                           aba_inputs[j].get, aba_outputs[j].put_nowait,
                           aba_bcast, aba_recvs[j].get)

        def rbc_send(k, o):
            send(k, ('ACS_RBC', j, o))

        # Only leader gets input
        rbc_input = input if j == pid else None
        rbc_recvs[j] = Queue()
        rbc = gevent.spawn(reliablebroadcast, sid+'RBC'+str(j), pid, N, f, j,
                           rbc_input, rbc_recvs[j].get, rbc_send)
        rbc_outputs[j] = rbc.get  # block for output from rbc

    for j in range(N): _setup(j)

    def _recv():
        while True:
            (sender, (tag, j, msg)) = recv()
            if   tag == 'ACS_COIN': coin_recvs[j].put_nowait((sender,msg))
            elif tag == 'ACS_RBC' : rbc_recvs [j].put_nowait((sender,msg))
            elif tag == 'ACS_ABA' : aba_recvs [j].put_nowait((sender,msg))
            else:
                print 'Unknown tag!!', tag
                raise
    gevent.spawn(_recv)

    return commonsubset(pid, N, f, rbc_outputs,
                        [_.put_nowait for _ in aba_inputs],
                        [_.get for _ in aba_outputs])

### Test asynchronous common subset
def _test_commonsubset(N=4, f=1, seed=None):
    # Generate keys
    sid = 'sidA'
    PK, SKs = dealer(N, f+1, seed=seed)
    rnd = random.Random(seed)
    #print 'SEED:', seed
    router_seed = rnd.random()
    sends, recvs = simple_router(N, seed=router_seed)

    inputs  = [None] * N
    threads = [None] * N
    for i in range(N):
        inputs[i] = Queue(1)

        threads[i] = gevent.spawn(_make_commonsubset, sid, i, N, f,
                                  PK, SKs[i],
                                  inputs[i].get, sends[i], recvs[i])

    for i in range(N):
        if i == 1: continue
        inputs[i].put('<[ACS Input %d]>' % i)

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

from nose2.tools import params

#@params(*range(100))
#def test_commonsubset(i):
#    _test_commonsubset(seed=i)
    #_test_commonsubset(seed=1)

def test_commonsubset():
    _test_commonsubset()
