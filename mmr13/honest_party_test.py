#!/usr/bin/python
__author__ = 'aluex'
from gevent import monkey
monkey.patch_all()

from gevent.queue import *
from gevent import Greenlet
from utils import bcolors, mylog, initiateThresholdSig
from includeTransaction import honestParty, Transaction
from collections import defaultdict
from bkr_acs import initBeforeBinaryConsensus
from utils import ACSException
import gevent
import os
#import random
from utils import myRandom as random
from utils import checkExceptionPerGreenlet, getSignatureCost, \
    deepEncode, deepDecode, randomTransaction, initiateECDSAKeys, finishTransactionLeap
# import fcp
import json
import cPickle as pickle
import time
import sys
import zlib
#print state
import base64
# import socks
import struct
from io import BytesIO

USE_DEEP_ENCODE = True
QUIET_MODE = True

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

msgCounter = 0
totalMessageSize = 0
starting_time = dict()
ending_time = dict()
msgSize = dict()
msgFrom = dict()
msgTo = dict()
msgContent = dict()
logChannel = Queue()
msgTypeCounter = [0]*6
logGreenlet = None

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        #if not QUIET_MODE:
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

def encode(m):  # TODO
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    #intermediate = deepEncode(msgCounter, m)
    if USE_DEEP_ENCODE:
        result = deepEncode(msgCounter, m)
    else:
        result = (msgCounter, m)
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
    if USE_DEEP_ENCODE:
        result = deepDecode(s, msgTypeCounter)
    else:
        result = s
    #result = deepDecode(zlib.decompress(s)) #pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    msgContent[result[0]] = None
    global totalMessageSize
    totalMessageSize += msgSize[result[0]]
    if not QUIET_MODE:
        logChannel.put((result[0], msgSize[result[0]], msgFrom[result[0]], msgTo[result[0]],
                    starting_time[result[0]], ending_time[result[0]], repr(result[1])))
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
    initiateThresholdSig(open(sys.argv[1], 'r').read())
    initiateECDSAKeys(open(sys.argv[2], 'r').read())
    buffers = map(lambda _: Queue(1), range(N))
    global logGreenlet
    logGreenlet = Greenlet(logWriter, open('msglog.TorMultiple', 'w'))
    logGreenlet.parent_args = (N, t)
    logGreenlet.name = 'client_test_freenet.logWriter'
    logGreenlet.start()

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                # mylog(bcolors.OKGREEN + "MSG: [%d] -> [%d]: %s" % (i, j, repr(v)) + bcolors.ENDC)
                buffers[j].put(encode((j, i, v)))
                # mylog(bcolors.OKGREEN + "     [%d] -> [%d]: Finish" % (i, j) + bcolors.ENDC)
            for j in range(N):
                Greenlet(_deliver, j).start()
                # Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    def recvWithDecode(buf):
        def recv():
            s = buf.get()
            return decode(s)[1:]
        return recv

    while True:
    #if True:
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = recvWithDecode(buffers[i])
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            controlChannels[i].put(('IncludeTransaction',
                set([randomTransaction() for trC in range(int(sys.argv[3]))])))
            #controlChannels[i].put(('IncludeTransaction', randomTransaction()))
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
        except finishTransactionLeap:  ### Manually jump to this level
            print msgTypeCounter
            # message id 0 (duplicated) for signatureCost
            #logChannel.put((0, getSignatureCost(), 0, 0, str(time.time()), str(time.time()), '[signature cost]'))
            logChannel.put(StopIteration)
            mylog("=====", verboseLevel=-1)
            for item in logChannel:
                mylog(item, verboseLevel=-1)
            mylog("=====", verboseLevel=-1)
            #checkExceptionPerGreenlet()
            # print getSignatureCost()
            continue
            pass
        except gevent.hub.LoopExit: # Manual fix for early stop
            while True:
                gevent.sleep(1)
            checkExceptionPerGreenlet()
        finally:
            print "Concensus Finished"

# import GreenletProfiler
import atexit
import gc
import traceback
from greenlet import greenlet

USE_PROFILE = False
# GEVENT_DEBUG = False
GEVENT_DEBUG = False
OUTPUT_HALF_MSG = False

def exit():
    print "Entering atexit()"
    mylog("Total Message size %d" % totalMessageSize, verboseLevel=-2)
    if OUTPUT_HALF_MSG:
        halfmsgCounter = 0
        for msgindex in starting_time.keys():
            if msgindex not in ending_time.keys():
                logChannel.put((msgindex, msgSize[msgindex], msgFrom[msgindex],
                    msgTo[msgindex], starting_time[msgindex], time.time(), '[UNRECEIVED]' + repr(msgContent[msgindex])))
                halfmsgCounter += 1
        mylog('%d extra log exported.' % halfmsgCounter, verboseLevel=-1)

    if GEVENT_DEBUG:
        checkExceptionPerGreenlet()

    if USE_PROFILE:
        GreenletProfiler.stop()
        stats = GreenletProfiler.get_func_stats()
        stats.print_all()
        stats.save('profile.callgrind', type='callgrind')

if __name__ == '__main__':
    # GreenletProfiler.set_clock_type('cpu')
    atexit.register(exit)
    if USE_PROFILE:
        GreenletProfiler.start()
    client_test_freenet(20, 4)

