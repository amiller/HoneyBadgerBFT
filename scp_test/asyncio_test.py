import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
import random

# Returns an idempotent function that only 
def makeCallOnce(callback):
    called = [False]
    def callOnce():
        if called[0]: return
        called[0] = True
        callback()
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


# Run the protocol with no corruptions, uniform random message delays
def random_delay_broadcast1(inputs, t):
    maxdelay = 0.01

    N = len(inputs)
    buffers = map(lambda _: Queue(1), inputs)

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                buffers[j].put((i,v))
            for j in range(N): 
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    def makeOutput(i):
        def _output(v):
            print '[%d]' % i, 'output:', v
        return _output
        
    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        outp = makeOutput(i)
        inp = bv_broadcast(i, N, t, bc, recv, outp)
        th = Greenlet(inp, inputs[i])
        th.start_later(random.random()*maxdelay)
        ts.append(th)


    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit: pass
