__author__ = 'aluex'

from gevent.queue import Queue
from gevent import Greenlet
from utils import bcolors, mylog
from includeTransaction import honestParty, Transaction
from collections import defaultdict
from bkr_acs import initBeforeBinaryConsensus
from utils import ACSException
import gevent
import os
#import random
from utils import myRandom as random
from gevent.server import StreamServer
import fcp
import json
import pickle
import time
import zlib
#print state

import socks

TOR_SOCKSPORT = range(9050, 9055)

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            #print 'line read from socket', line
            obj = decode(line)
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
            s.sendall(encode(obj) + '\n')
    Greenlet(_handle).start()
    return q

BASE_PORT = 49500

TOR_MAPPING_LIST = """
3lejkcwieaamk2ea.onion
l2y6c2tztpjbcjv5.onion
cystbatihmcyj6nf.onion
hhhegzzwem6v2rpx.onion
za44dm5gbhkzif24.onion
""".strip().split('\n')

TOR_MAPPINGS = [(host, BASE_PORT+i) for i, host in enumerate(TOR_MAPPING_LIST)]
mylog("[INIT] TOR_MAPPINGS: %s" % repr(TOR_MAPPINGS))

nameList = ["Alice", "Bob", "Christina", "David", "Eco", "Francis", "Gerald", "Harris", "Ive", "Jessica"]

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

def randomTransaction():
    tx = Transaction()
    tx.source = random.choice(nameList)
    tx.target = random.choice(nameList)
    tx.amount = random.randint(1, 100)
    return tx

def randomTransactionStr():
    return repr(randomTransaction())

msgCounter = 0
starting_time = dict()
ending_time = dict()
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, st, et, content = logChannel.get()
        fileHandler.write("%d[%s]-[%s]%s\n" % (msgCounter, st, et, content))
        fileHandler.flush()

def encode(m):
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = time.strftime('[%m-%d-%y|%H:%M:%S]')
    result = zlib.compress(
        pickle.dumps((msgCounter, m)),
    9)  # Highest compression level
    return result

def decode(s):
    result = pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = time.strftime('[%m-%d-%y|%H:%M:%S]')
    logChannel.put((result[0], starting_time[result[0]], ending_time[result[0]], result[1]))
    return result[1]

def client_test_freenet(N, t):
    '''
    Test for the client with random delay channels

    command list
        i [target]: send a transaction to include for some particular party
        h [target]: stop some particular party
        m [target]: manually make particular party send some message
        help: show the help screen

    :param N: the number of parties
    :param t: the number of malicious parties
    :return None:
    '''

    #buffers = map(lambda _: Queue(1), range(N))
    Greenlet(logWriter, open('msglog.TorMultiple', 'w')).start()
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
                chans[j].put((i, v))
        return _broadcast

    servers = []
    for i in range(N):
        _, port = TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))
    gevent.sleep(2)
    print 'servers started'

    #while True:
    if True:  # We only test for once
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = servers[i].get
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            #controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            controlChannels[i].put(('IncludeTransaction', randomTransactionStr()))
            th.start()
            ts.append(th)

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)

if __name__ == '__main__':
    client_test_freenet(5, 1)
