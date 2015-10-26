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
import fcp
import json
import cPickle as pickle
import time
import zlib
#print state
import base64
import socks
import struct
from io import BytesIO

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
msgContent = dict()
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
    maxdelay = 0.01
    buffers = map(lambda _: Queue(1), range(N))
    gtemp = Greenlet(logWriter, open('msglog.TorMultiple', 'w'))
    gtemp.parent_args = (N, t)
    gtemp.name = 'client_test_freenet.logWriter'
    gtemp.start()

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                # mylog(bcolors.OKGREEN + "MSG: [%d] -> [%d]: %s" % (i, j, repr(v)) + bcolors.ENDC)
                buffers[j].put(encode((j, i, v)))
                # mylog(bcolors.OKGREEN + "     [%d] -> [%d]: Finish" % (i, j) + bcolors.ENDC)
            for j in range(N):
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    def recvWithDecode(buf):
        def recv():
            s = buf.get()
            return decode(s)[1:]
        return recv

    #while True:
    if True:
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = recvWithDecode(buffers[i])
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            th.start_later(random.random() * maxdelay)
            ts.append(th)

        #def monitorUserInput(): # No idea why raw_input will block the whole gevent, need some investigation
        #    while True:
        #        mylog(">>>")
        #        tokens = [s for s in raw_input().strip().split() if s]
        #        mylog("= %s\n" % repr(parser[tokens[0]](tokens)))

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)
            #tokens = [s for s in raw_input().strip().split() if s]
            #mylog("= %s\n" % repr(parser[tokens[0]](tokens)))  # In case the parser has an output

import GreenletProfiler
import atexit
import gc
import traceback
from greenlet import greenlet

USE_PROFILE = False


def exit():
    halfmsgCounter = 0
    for msgindex in starting_time.keys():
        if msgindex not in ending_time.keys():
            logChannel.put((msgindex, msgSize[msgindex], msgFrom[msgindex],
                msgTo[msgindex], starting_time[msgindex], time.time(), '[UNRECEIVED]' + repr(msgContent[msgindex])))
            halfmsgCounter += 1
    mylog('%d extra log exported.' % halfmsgCounter, verboseLevel=-1)

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
    GreenletProfiler.set_clock_type('cpu')
    atexit.register(exit)
    if USE_PROFILE:
        GreenletProfiler.start()
    client_test_freenet(20, 4)

