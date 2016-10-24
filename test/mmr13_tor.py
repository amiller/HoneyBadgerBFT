# Basic framework requirements
from gevent import monkey
monkey.patch_all()

import gevent
from gevent import Greenlet
from gevent.server import StreamServer
from gevent.queue import Queue
import json

# Import the algorithm
from ..core.broadcasts import makeCallOnce, bv_broadcast, shared_coin_dummy

# Sockets that route through Tor
import socket
import socks
socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9050, True)
    
def listen_to_channel(port):
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            obj = json.loads(line)
            q.put(obj)
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port):
    s = socks.socksocket()
    s.connect((hostname, port))
    q = Queue(1)
    def _handle():
        while True:
            obj = q.get()
            s.sendall(json.dumps(obj) + '\n')
    Greenlet(_handle).start()
    return q

TOR_MAPPINGS = [
('t6wgydamj55qs7do.onion',49500),
('qk7v4tpkwnslwfvb.onion',49501),
('cs25ak52h4efslwp.onion',49502),
('7vcug2izpf5psowt.onion',49503)
]

# Run the BV_broadcast protocol with no corruptions and uniform random message delays
def random_delay_broadcast_tor(inputs, t):

    N = len(inputs)

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        chans = []
        # First establish N connections (including a self connection)
        for j in range(N):
            host,port = TOR_MAPPINGS[j]
            chans.append(connect_to_channel(host,port))
        def _broadcast(v):
            for j in range(N):
                chans[j].put( (i,v) )
        return _broadcast

    # Get the servers ready
    def makeOutput(i):
        def _output(v):
            print '[%d]' % i, 'output:', v
        return _output

    # Create the servers
    servers = []
    for i in range(N):
        _,port = TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))
    gevent.sleep(2)
    print 'servers started'
        
    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = servers[i].get
        outp = makeOutput(i)
        inp = bv_broadcast(i, N, t, bc, recv, outp)
        th = Greenlet(inp, inputs[i])
        th.start()
        ts.append(th)

    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit: pass
