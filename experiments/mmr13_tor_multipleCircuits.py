from gevent import monkey
monkey.patch_all()

import gevent
from gevent import Greenlet
from gevent.server import StreamServer
from gevent.queue import Queue
import json

import random

from ..core.broadcasts import bv_broadcast, shared_coin_dummy, binary_consensus, bcolors, mylog, mv84consensus, globalState

import socks

TOR_SOCKSPORT = range(9050, 9055)

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            #print 'line read from socket', line
            obj = json.loads(line)
            q.put(obj)
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, party):
    s = socks.socksocket()
    s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", TOR_SOCKSPORT[party], True)
    s.connect((hostname, port))
    q = Queue(1)
    def _handle():
        while True:
            obj = q.get()
            s.sendall(json.dumps(obj) + '\n')
    Greenlet(_handle).start()
    return q

BASE_PORT = 49500

TOR_MAPPING_LIST = """
3lejkcwieaamk2ea.onion
l2y6c2tztpjbcjv5.onion
cystbatihmcyj6nf.onion
hhhegzzwem6v2rpx.onion
za44dm5gbhkzif24.onion
""".strip().split('\n')  # hard-coded test




TOR_MAPPINGS = [(host, BASE_PORT+i) for i, host in enumerate(TOR_MAPPING_LIST)]
mylog("[INIT] TOR_MAPPINGS: %s" % repr(TOR_MAPPINGS))

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
def random_delay_binary_consensus(N, t):
    maxdelay = 0.01

    buffers = map(lambda _: Queue(1), range(N))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                mylog(bcolors.OKGREEN + "MSG: [%d] -> [%d]: %s" % (i, j, repr(v)) + bcolors.ENDC)
                buffers[j].put((i,v))
                mylog(bcolors.OKGREEN + "     [%d] -> [%d]: Finish" % (i, j) + bcolors.ENDC)
            for j in range(N):
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = buffers[i].get
        vi = random.randint(0, 1)
        decideChannel = Queue(1)
        th = Greenlet(binary_consensus, i, N, t, vi, decideChannel, bc, recv)
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


# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_multivalue_consensus(N, t, inputs):

    mylog("[Tor] Making circuits...")

    # Now we don't use stem

    maxdelay = 0.01

    buffers = map(lambda _: Queue(1), range(N))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        chans = []
        # First establish N connections (including a self connection)
        for j in range(N):
            host, port = TOR_MAPPINGS[j]
            chans.append(connect_to_channel(host, port, i))
        def _broadcast(v):
            mylog(bcolors.OKGREEN + "[%d] Broadcasted %s" % (i, repr(v)) + bcolors.ENDC)
            for j in range(N):
                chans[j].put( (i,v) )
        return _broadcast

    # Create the servers
    servers = []
    for i in range(N):
        _, port = TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))
    gevent.sleep(2)
    print 'servers started'


    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = servers[i].get
        vi = inputs[i]
        th = Greenlet(mv84consensus, i, N, t, vi, bc, recv)
        th.start() # start_later(random.random() * maxdelay)
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
    print "Testing multivalue consensus with different inputs..."
    random_delay_multivalue_consensus(5, 1, [random.randint(0, 10) for x in range(5)])

