from gevent import monkey
monkey.patch_all()

import gevent
from gevent import Greenlet
from gevent.queue import Queue
import random

from ..core.broadcasts import bv_broadcast, binary_consensus, bcolors, mylog, mv84consensus, globalState


# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_broadcast1(inputs, t):
    maxdelay = 0.01

    N = len(inputs)
    buffers = map(lambda _: Queue(1), inputs)

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
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
                buffers[j].put((i,v))
            for j in range(N): 
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    def _run(i, coin):
        # Party i, continue to run the shared coin
        r = 0
        while r < 5:
            gevent.sleep(random.random() * maxdelay)
            print '[',i,'] at round ', r
            b = next(coin)
            print '[',i,'] bit[%d]:'%r, b
            r += 1
        print '[',i,'] done'
        
    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        coin = shared_coin_dummy(i, N, t, bc, recv)
        th = Greenlet(_run, i, coin)
        th.start_later(random.random() * maxdelay)
        ts.append(th)

    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit: pass

# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_binary_consensus(N, t, inputs):
    maxdelay = 0.01

    buffers = map(lambda _: Queue(1), range(N))
    random_delay_binary_consensus.msgCount = 0
    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                random_delay_binary_consensus.msgCount += 1
                tmpCount = random_delay_binary_consensus.msgCount
                mylog(bcolors.OKGREEN + "MSG: [%d] -[%d]-> [%d]: %s" % (i, tmpCount, j, repr(v)) + bcolors.ENDC)
                buffers[j].put((i, v))
                mylog(bcolors.OKGREEN + "     [%d] -[%d]-> [%d]: Finish" % (i, tmpCount, j) + bcolors.ENDC)
            for j in range(N):
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        vi = inputs[i]  #random.randint(0, 1)
        decideChannel = Queue(1)
        th = Greenlet(binary_consensus, i, N, t, vi, decideChannel, bc, recv)
        th.start_later(random.random() * maxdelay)
        ts.append(th)



    gevent.joinall(ts)

    for key, item in globalState.items():
        if item != globalState[0]:
            mylog(bcolors.FAIL + 'Bad Concensus!' + bcolors.ENDC)

    print globalState


# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_multivalue_consensus(N, t, inputs):
    maxdelay = 0.01

    msgThreads = []

    buffers = map(lambda _: Queue(1), range(N))

    random_delay_multivalue_consensus.msgCount = 0
    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                random_delay_multivalue_consensus.msgCount += 1
                tmpCount = random_delay_multivalue_consensus.msgCount
                mylog(bcolors.OKGREEN + "MSG: [%d] -[%d]-> [%d]: %s" % (i, tmpCount, j, repr(v)) + bcolors.ENDC)
                buffers[j].put((i,v))
                mylog(bcolors.OKGREEN + "     [%d] -[%d]-> [%d]: Finish" % (i, tmpCount, j) + bcolors.ENDC)

            for j in range(N):
                g = Greenlet(_deliver, j)
                g.start_later(random.random()*maxdelay)
                msgThreads.append(g)  # Keep reference
        return _broadcast

    ts = []
    #cid = 1
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        vi = inputs[i]
        th = Greenlet(mv84consensus, i, N, t, vi, bc, recv)
        th.start_later(random.random() * maxdelay)
        ts.append(th)

    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit: # Manual fix for early stop
        agreed = ""
        for key, value in globalState.items():
            if globalState[key] != "":
                agreed = globalState[key]
        for key,  value in globalState.items():
            if globalState[key] == "":
                globalState[key] = agreed
            if globalState[key] != agreed:
                print "Consensus Error"


    print globalState

if __name__=='__main__':
    print "[ =========== ]"
    print "Testing binary consensus..."
    inputs = [random.randint(0, 1) for _ in range(5)]
    print "Inputs:", inputs
    random_delay_binary_consensus(5, 1, inputs)

