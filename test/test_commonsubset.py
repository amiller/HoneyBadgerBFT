import unittest
import gevent
import random
from gevent.event import Event
from gevent.queue import Queue
import core.commoncoin
reload(core.commoncoin)
import core.binaryagreement
reload(core.binaryagreement)
import core.reliablebroadcast
reload(core.reliablebroadcast)
import core.commonsubset
reload(core.commonsubset)
from core.commoncoin import shared_coin
from core.binaryagreement import binaryagreement
from core.reliablebroadcast import reliablebroadcast
from core.commonsubset import commonsubset
from crypto.threshsig.boldyreva import dealer
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
            #print 'SEND   %8s [%2d -> %2d] %2.1f' % (o[0], i, j, delay*1000), o[1:]
            gevent.spawn_later(delay, queues[j].put, (i,o))
        return _send

    def makeRecv(j):
        def _recv():
            (i,o) = queues[j].get()
            #print 'RECV %8s [%2d -> %2d]' % (o[0], i, j)
            return (i,o)
        return _recv
        
    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])



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

        coin_recvs[j] = Queue(1)
        coin = shared_coin(sid + 'COIN' + str(j), pid, N, f, PK, SK,
                           coin_bcast, coin_recvs[j].get)

        def aba_bcast(o):
            broadcast(('ACS_ABA', j, o))

        aba_recvs[j] = Queue(1)
        aba = gevent.spawn(binaryagreement, pid, N, f, coin,
                           aba_inputs[j].get, aba_outputs[j].put,
                           aba_bcast, aba_recvs[j].get)

        def rbc_send(k, o):
            send(k, ('ACS_RBC', j, o))

        # Only leader gets input
        rbc_input = input if j == pid else None
        rbc_recvs[j] = Queue(1)
        rbc = gevent.spawn(reliablebroadcast, pid, N, f, j,
                           rbc_input, rbc_recvs[j].get, rbc_send)
        rbc_outputs[j] = rbc.get  # block for output from rbc

    for j in range(N): _setup(j)
        
    def _recv():
        while True:
            (sender, (tag, j, msg)) = recv()
            if   tag == 'ACS_COIN': coin_recvs[j].put((sender,msg))
            elif tag == 'ACS_RBC' : rbc_recvs [j].put((sender,msg))
            elif tag == 'ACS_ABA' : aba_recvs [j].put((sender,msg))
            else:
                print 'Unknown tag!!', tag
                raise
    gevent.spawn(_recv)

    return commonsubset(pid, N, f, rbc_outputs,
                        [_.put for _ in aba_inputs],
                        [_.get for _ in aba_outputs])

### Test asynchronous common subset
def _test_commonsubset(N=4, f=1, seed=None):
    # Generate keys
    sid = 'sidA'
    PK, SKs = dealer(N, f+1)
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = simple_router(N, seed=seed)

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

def test_commonsubset():
    _test_commonsubset()
