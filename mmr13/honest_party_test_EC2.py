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
#import fcp
#import json
#import cPickle as pickle
import time
#import zlib
#print state
import base64
import socks, socket
import struct
from io import BytesIO
import sys
from subprocess import check_output

TOR_SOCKSPORT = range(9050, 9150)
WAITING_SETUP_TIME_IN_SEC = 3

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            # print 'line read from socket', line
            obj = decode(base64.b64decode(line))
            # mylog('decoding')
            # mylog(obj, verboseLevel=-1)
            q.put(obj[1:])
            # mylog(bcolors.OKBLUE + 'received %s' % repr(obj[1:]) + bcolors.ENDC, verboseLevel=-1)
    server = StreamServer(('0.0.0.0', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, party):
    mylog('Trying to connect to %s for party %d' % (repr((hostname, port)), party), verboseLevel=-1)
    retry = True
    s = socks.socksocket()
    while retry:
      try:
        s = socks.socksocket()
        # s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", TOR_SOCKSPORT[party], True)
        s.connect((hostname, port))
        retry = False
      except Exception, e:  # socks.SOCKS5Error:
        retry = True
        gevent.sleep(1)
        s.close()
        mylog('retrying (%s, %d) caused by %s...' % (hostname, port, str(e)) , verboseLevel=-1)
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
                
    gtemp = Greenlet(_handle)
    gtemp.parent_args = (hostname, port, party)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

BASE_PORT = 49500

def getAddrFromEC2Summary(s):
    return [
    x.split('ec2.')[-1] for x in s.replace(
    '.compute.amazonaws.com', ''
).replace(
    '.us-west-1', ''    # Later we need to add more such lines
).replace(
    '-', '.'
).strip().split('\n')]

IP_LIST = None
IP_MAPPINGS = None  # [(host, BASE_PORT) for i, host in enumerate(IP_LIST)]


def prepareIPList(content):
    global IP_LIST, IP_MAPPINGS
    IP_LIST = content.strip().split('\n')  # getAddrFromEC2Summary(content)
    IP_MAPPINGS = [(host, BASE_PORT) for host in IP_LIST if host]
    #print IP_LIST

# TOR_MAPPINGS = [(host, BASE_PORT+i) for i, host in enumerate(TOR_MAPPING_LIST)]

mylog("[INIT] IP_MAPPINGS: %s" % repr(IP_MAPPINGS))

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
starting_time = defaultdict(lambda: 0.0)
ending_time = defaultdict(lambda: 0.0)
msgSize = defaultdict(lambda: 0)
msgFrom = defaultdict(lambda: 0)
msgTo = defaultdict(lambda: 0)
msgContent = defaultdict(lambda: '')
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

class deepEncodeException(Exception):
    pass

class deepDecodeException(Exception):
    pass

def encodeTransaction(tr):
    sourceInd = nameList.index(tr.source)
    targetInd = nameList.index(tr.target)
    return struct.pack(
        '<BBH', sourceInd, targetInd, tr.amount
    )

def deepEncode(mc, m):
    buf = BytesIO()
    buf.write(struct.pack('<I', mc))
    f, t, (tag, c) = m
    buf.write(struct.pack('BB', f, t))
    # totally we have 4 msg types
    if c[0]=='i':
        buf.write('\x01')
        t2, p1, s = c
        buf.write(struct.pack('B', p1))
        for tr in s:
            buf.write(encodeTransaction(tr))
    elif c[0]=='e':
        buf.write('\x02')
        t2, p1, (p2, s) = c
        buf.write(struct.pack('BB', p1, p2))
        for tr in s:
            buf.write(encodeTransaction(tr))
    else:
        p1, (t2, (p2, p3)) = c
        if t2 == 'B':
            buf.write('\x03')
        elif t2 == 'A':
            buf.write('\x04')
        else:
            raise deepEncodeException()
        buf.write(struct.pack('BBB', p1, p2, p3))
    buf.seek(0)
    return buf.read()

def constructTransactionFromRepr(r):
    sourceInd, targetInd, amount = struct.unpack('<BBH', r)
    tr = Transaction()
    tr.source = nameList[sourceInd]
    tr.target = nameList[targetInd]
    tr.amount = amount
    return tr

# Msg Types:
# 1:(3, 1, ('B', ('i', 1, set([{{Transaction from Francis to Eco with 86}}]))))
# 2:(1, 0, ('B', ('e', 0, (2, set([{{Transaction from Bob to Jessica with 65}}])))))
# 3:(0, 3, ('A', (1, ('B', (1, 1)))))
# 4:(0, 3, ('A', (2, ('A', (1, 1)))))

def deepDecode(m):
    buf = BytesIO(m)
    mc, f, t, msgtype = struct.unpack('<IBBB', buf.read(7))
    trSet = set()
    if msgtype == 1:
        p1, = struct.unpack('B', buf.read(1))
        trRepr = buf.read(4)
        while trRepr:
            trSet.add(constructTransactionFromRepr(trRepr))
            trRepr = buf.read(4)
        return mc, (f, t, ('B', ('i', p1, trSet)),)
    elif msgtype == 2:
        p1, p2 = struct.unpack('BB', buf.read(2))
        trRepr = buf.read(4)
        while trRepr:
            trSet.add(constructTransactionFromRepr(trRepr))
            trRepr = buf.read(4)
        return mc, (f, t, ('B', ('e', p1, (p2, trSet))),)
    elif msgtype == 3:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('B', (p2, p3)))),)
    elif msgtype == 4:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('A', (p2, p3)))),)
    else:
        raise deepDecodeException()

def encode(m):  # TODO
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    #intermediate = deepEncode(msgCounter, m)
    result = deepEncode(msgCounter, m)
    #result = zlib.compress(
    #    #pickle.dumps(deepEncode(msgCounter, m)),
    #    intermediate,
    #9)  # Highest compression level
    #print 'intermediateLen', len(intermediate), 'compressed', len(result)
    msgSize[msgCounter] = len(result)
    msgFrom[msgCounter] = m[1]
    msgTo[msgCounter] = m[0]
    msgContent[msgCounter] = m
    return result

def decode(s):  # TODO
    result = deepDecode(s)
    #result = deepDecode(zlib.decompress(s)) #pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    msgContent[result[0]] = None
    msgFrom[result[0]] = result[1][1]
    msgTo[result[0]] = result[1][0]
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
    # query amazon meta-data
    localIP = check_output(['curl', 'http://169.254.169.254/latest/meta-data/public-ipv4'])  #  socket.gethostbyname(socket.gethostname())
    myID = IP_LIST.index(localIP)
    N = len(IP_LIST)
    mylog("[%d] Parameters: N %d, t %d" % (myID, N, t), verboseLevel=-1)
    mylog("[%d] IP_LIST: %s" % (myID, IP_LIST), verboseLevel=-1)
    #buffers = map(lambda _: Queue(1), range(N))
    gtemp = Greenlet(logWriter, open('msglog.TorMultiple', 'w'))
    gtemp.parent_args = (N, t)
    gtemp.name = 'client_test_freenet.logWriter'
    gtemp.start()
    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        chans = []
        # First establish N connections (including a self connection)
        for j in range(N):
            host, port = IP_MAPPINGS[j] # TOR_MAPPINGS[j]
            chans.append(connect_to_channel(host, port, i))
        def _broadcast(v):
            mylog(bcolors.OKGREEN + "[%d] Broadcasted %s" % (i, repr(v)) + bcolors.ENDC, verboseLevel=-1)
            for j in range(N):
                chans[j].put((j, i, v))  # from i to j
        return _broadcast
    iterList = [myID] #range(N)
    servers = []
    for i in iterList:
        _, port = IP_MAPPINGS[i] # TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))
    #gevent.sleep(2)
    print 'servers started'

    gevent.sleep(WAITING_SETUP_TIME_IN_SEC) # wait for set-up to be ready

    #while True:
    if True:  # We only test for once
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        bcList = dict()
        tList = []

        def _makeBroadcast(x):
            bc = makeBroadcast(x)
            bcList[x] = bc

        for i in iterList:
            tmp_t = Greenlet(_makeBroadcast, i)
            tmp_t.parent_args = (N, t)
            tmp_t.name = 'client_test_freenet._makeBroadcast(%d)' % i
            tmp_t.start()
            tList.append(tmp_t)
        gevent.joinall(tList)

        for i in iterList:
            bc = bcList[i]  # makeBroadcast(i)
            #recv = servers[i].get
            recv = servers[0].get
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            th.parent_args = (N, t)
            th.name = 'client_test_freenet.honestParty(%d)' % i
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            th.start()
            mylog('Summoned party %i at time %f' % (i, time.time()), verboseLevel=-1)
            ts.append(th)

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)


import atexit
import gc
import traceback
from greenlet import greenlet

USE_PROFILE = False
GEVENT_DEBUG = False
OUTPUT_HALF_MSG = False

if USE_PROFILE:
    import GreenletProfiler

def exit():
    if OUTPUT_HALF_MSG:
        halfmsgCounter = 0
        for msgindex in starting_time.keys():
            if msgindex not in ending_time.keys():
                logChannel.put((msgindex, msgSize[msgindex], msgFrom[msgindex],
                    msgTo[msgindex], starting_time[msgindex], time.time(), '[UNRECEIVED]' + repr(msgContent[msgindex])))
                halfmsgCounter += 1
        mylog('%d extra log exported.' % halfmsgCounter, verboseLevel=-1)

    if GEVENT_DEBUG:
        for ob in gc.get_objects():
            if not hasattr(ob, 'parent_args'):
                continue
            if not ob:
                continue
            if not ob.exception:
                continue
            mylog('%s[%s] called with parent arg\n(%s)\n%s' % (ob.name, repr(ob.args), repr(ob.parent_args),
                ''.join(traceback.format_stack(ob.gr_frame))), verboseLevel=-1)

    if USE_PROFILE:
        GreenletProfiler.stop()
        stats = GreenletProfiler.get_func_stats()
        stats.print_all()
        stats.save('profile.callgrind', type='callgrind')

if __name__ == '__main__':
    if USE_PROFILE:
        GreenletProfiler.set_clock_type('cpu')
    atexit.register(exit)
    prepareIPList(open(sys.argv[1], 'r').read())
    if USE_PROFILE:
        GreenletProfiler.start()
    client_test_freenet(4, 1)  # Here N is no longer used

