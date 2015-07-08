import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
import random


# Returns an idempotent function that only 
def makeCallOnce(callback, *args):
    called = [False]
    def callOnce():
        if called[0]: return
        called[0] = True
        callback(*args)
    return callOnce

# The BV_Broadcast algorithm from [MMR13]
def bv_broadcast(pid, N, t, broadcast, receive, output):
    assert N > 3*t

    def input(v):
        assert v in (0,1)
        broadcast(v)

        received = defaultdict(set)
        def _bc(v):
            print '[%d]' % pid, 'Relaying', v
            broadcast(v)
        relay0 = makeCallOnce(lambda: _bc(0))
        relay1 = makeCallOnce(lambda: _bc(1))
        out0 = makeCallOnce(lambda: output(0))
        out1 = makeCallOnce(lambda: output(1))

        while True:
            (pid, v) = receive()
            assert v in (0,1)
            assert pid in range(N)
            received[v].add(pid)
            if len(received[v]) >= t + 1:
                (relay0,relay1)[v]()
            if len(received[v]) >= 2*t + 1:
                (out0,out1)[v]()

    return input

# A dummy version of the Shared Coin
def shared_coin_dummy(pid, N, t, broadcast, receive):
    received = defaultdict(set)
    outputQueue = defaultdict(lambda:Queue(1))
    round = [0]
    def _recv():
        while True:
            # Receive P_i's share of value r
            (i,r) = receive()
            assert i in range(N)
            assert r >= 0
            if i in received[r]: continue
            received[r].add(i)
            if len(received[r]) == N-t: 
                # We've collected enough shares
                b = hash(r) % 2
                outputQueue[r].put(b)
    Greenlet(_recv).start()
    def _next():
        r = round[0]
        # Broadcast our share
        broadcast(r)
        # Wait until the value is ready
        b = outputQueue[r].get()
        # Advance round
        round[0] += 1
        return b

    return _next

def binary_consensus(pid, N, t, vi, broadcast, receive):
    # Messages received are routed to either a shared coin, the broadcast, or AUX
    coinQ = Queue(1)
    bcQ = Queue(1)
    def _recv():
        while True:
            (i, (tag, m)) = receive()
            if tag == 'BC': 
                # Broadcast message
                r, msg = m
                bcQ[r].put( (i, msg) )
            elif tag == 'COIN':
                # A share of a coin
                coinQ.put(m)
            elif tag == 'AUX':
                # Aux message
                # TODO: add aux message to queue
                pass

    def make_bvbc_bc(r):
        def _bc(m):
            broadcast( ('BC', (r, m)) )
        return _bc

    Greenlet(_recv).start()
    
    round = 0
    est = vi
    while True:
        # Broadcast EST
        # TODO: let bv_broadcast receive
        bv_broadcast(pid, N, t, vi, make_bvbc_bc(round), None)(est)

        # TODO: fork to collect values output by bv_broadcast
        # TODO: wait for one value to be collected by bv_broadcast

        round += 1
