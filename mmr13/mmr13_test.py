import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
import random

import mmr13
reload(mmr13)
from mmr13 import makeCallOnce, bv_broadcast, shared_coin



# Run the BV_broadcast protocol with no corruptions and uniform random message delays
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


# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_sharedcoin_dummy(N, t):
    maxdelay = 0.01

    buffers = map(lambda _: Queue(1), range(N))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                buffers[j].put((i,v))
            for j in range(N): 
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    def _run(i, coin):
        # Party i, continue to run the shared coin
        r = 0
        while r < 5:
            gevent.sleep(random.random()*maxdelay)
            print '[',i,'] at round ', r
            b = coin()
            print '[',i,'] bit[%d]:'%r, b
            r += 1
        print '[',i,'] done'
        
    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        coin = shared_coin(i, N, t, bc, recv)
        th = Greenlet(_run, i, coin)
        th.start_later(random.random()*maxdelay)
        ts.append(th)

    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit: pass
