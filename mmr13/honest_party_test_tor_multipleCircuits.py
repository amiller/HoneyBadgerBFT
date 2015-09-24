#!/usr/bin/python
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
import cPickle as pickle
import time
import zlib
#print state
import base64
import socks

TOR_SOCKSPORT = range(9050, 9070)

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            #print 'line read from socket', line
            obj = decode(base64.b64decode(line))
            q.put(obj[1:])
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, party):
    retry = True
    if True:  #while retry:
      #try:
        s = socks.socksocket()
        s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", TOR_SOCKSPORT[party], True)
        s.connect((hostname, port))
        retry = False
      #except:  # socks.SOCKS5Error:
      #  retry = True
      #  mylog('retrying...', verboseLevel=-1)
    q = Queue(1)
    def _handle():
        while True:
            obj = q.get()
            retry = True
            s.sendall(base64.b64encode(encode(obj)) + '\n')
            #        retry = False
            #    except:
            #        retry = True
            #        mylog('retrying...', verboseLevel=-1)
                
    Greenlet(_handle).start()
    return q

BASE_PORT = 49500

TOR_MAPPING_LIST = """
3lejkcwieaamk2ea.onion
l2y6c2tztpjbcjv5.onion
cystbatihmcyj6nf.onion
hhhegzzwem6v2rpx.onion
za44dm5gbhkzif24.onion
gjbcxcdek272x5kv.onion
bgge235qrp2vc67b.onion
qd5pf7tlzv7tgvfm.onion
2gexsunkq5bruu2q.onion
alh6vi2fwxobluq5.onion
f3oqs4hq6lo6a7xl.onion
5hrnuw7iz2fnfgkv.onion
ijjkdw6fnrdhgt3d.onion
l5yd4jelejc2gl3i.onion
yyrdvlvucwbig56a.onion
fpcak233m6ohegms.onion
p2wvpc3tkdfqog6j.onion
5phvu6syhjbm7n3w.onion
hcgkkdxwvsc5qswe.onion
udaba767u7aocmty.onion
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
msgSize = dict()
msgFrom = dict()
msgTo = dict()
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

def encode(m):
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    result = zlib.compress(
        pickle.dumps((msgCounter, m[2])),
    9)  # Highest compression level
    msgSize[msgCounter] = len(result)
    msgFrom[msgCounter] = m[1]
    msgTo[msgCounter] = m[0]
    return result

def decode(s):
    result = pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    logChannel.put((result[0], msgSize[result[0]], msgFrom[result[0]], msgTo[result[0]], starting_time[result[0]], ending_time[result[0]], result[1]))
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
            mylog(bcolors.OKGREEN + "[%d] Broadcasted %s" % (i, repr(v)) + bcolors.ENDC, verboseLevel=-1)
            for j in range(N):
                chans[j].put((j, i, v))  # from i to j
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
            # controlChannels[i].put(('IncludeTransaction', randomTransactionStr()))
            th.start()
            mylog('Summoned party %i at time %f' % (i, time.time()), verboseLevel=-1)
            ts.append(th)
        for i in range(N):
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)

import GreenletProfiler
import atexit
def exit():
    GreenletProfiler.stop()
    stats = GreenletProfiler.get_func_stats()
    stats.print_all()
    stats.save('profile.callgrind', type='callgrind')

if __name__ == '__main__':
    GreenletProfiler.set_clock_type('cpu')
    # GreenletProfiler.start()
    # atexit.register(exit)
    client_test_freenet(6, 0)

