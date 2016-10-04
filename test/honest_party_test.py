#!/usr/bin/python
__author__ = 'aluex'
from gevent import monkey
monkey.patch_all()

from gevent.queue import *
from gevent import Greenlet
from ..core.utils import bcolors, mylog, initiateThresholdSig
from ..core.includeTransaction import honestParty
from ..core.bkr_acs import initBeforeBinaryConsensus
import gevent
import os
from ..core.utils import myRandom as random
from ..core.utils import ACSException, checkExceptionPerGreenlet, getSignatureCost, encodeTransaction, getKeys,  \
    deepEncode, deepDecode, randomTransaction, initiateECDSAKeys, initiateThresholdEnc, finishTransactionLeap

import time
import math
from ..commoncoin.boldyreva_gipc import initialize as initializeGIPC

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
msgTypeCounter = [[0, 0] for _ in range(8)]
logGreenlet = None

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

def encode(m):  # TODO
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())
    if USE_DEEP_ENCODE:
        result = deepEncode(msgCounter, m)
    else:
        result = (msgCounter, m)
    if m[0] == m[1] and m[2][0]!='O' and m[2][1][0] == 'e':
        ### this is a self to self echo message
        msgSize[msgCounter] = 0
    else:
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
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())
    msgContent[result[0]] = None
    global totalMessageSize
    totalMessageSize += msgSize[result[0]]
    if not QUIET_MODE:
        logChannel.put((result[0], msgSize[result[0]], msgFrom[result[0]], msgTo[result[0]],
                    starting_time[result[0]], ending_time[result[0]], repr(result[1])))
    return result[1]

def client_test_freenet(N, t, options):
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
    initiateThresholdSig(open(options.threshold_keys, 'r').read())
    initiateECDSAKeys(open(options.ecdsa, 'r').read())
    initiateThresholdEnc(open(options.threshold_encs, 'r').read())
    initializeGIPC(getKeys()[0])
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
                buffers[j].put(encode((j, i, v)))
            for j in range(N):
                Greenlet(_deliver, j).start()
        return _broadcast

    def recvWithDecode(buf):
        def recv():
            s = buf.get()
            return decode(s)[1:]
        return recv

    def makeSend(i):  # point to point message delivery
        def _send(j, v):
            buffers[j].put(encode((j, i, v)))
        return _send

    while True:
    #if True:
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        transactionSet = set([encodeTransaction(randomTransaction()) for trC in range(int(options.tx))])  # we are using the same one
        for i in range(N):
            bc = makeBroadcast(i)
            recv = recvWithDecode(buffers[i])
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv, makeSend(i), options.B)
            controlChannels[i].put(('IncludeTransaction', transactionSet))
            th.start_later(random.random() * maxdelay)
            ts.append(th)

        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except finishTransactionLeap:  ### Manually jump to this level
            print 'msgCounter', msgCounter
            print 'msgTypeCounter', msgTypeCounter
            # message id 0 (duplicated) for signatureCost
            logChannel.put(StopIteration)
            mylog("=====", verboseLevel=-1)
            for item in logChannel:
                mylog(item, verboseLevel=-1)
            mylog("=====", verboseLevel=-1)
            continue
        except gevent.hub.LoopExit:  # Manual fix for early stop
            while True:
                gevent.sleep(1)
            checkExceptionPerGreenlet()
        finally:
            print "Concensus Finished"

# import GreenletProfiler
import atexit

USE_PROFILE = False
GEVENT_DEBUG = False
OUTPUT_HALF_MSG = False

if USE_PROFILE:
    import GreenletProfiler

def exit():
    print "Entering atexit()"
    print 'msgCounter', msgCounter
    print 'msgTypeCounter', msgTypeCounter
    nums,lens = zip(*msgTypeCounter)
    print '    Init      Echo      Val       Aux      Coin     Ready    Share'
    print '%8d %8d %9d %9d %9d %9d %9d' % nums[1:]
    print '%8d %8d %9d %9d %9d %9d %9d' % lens[1:]
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
        GreenletProfiler.set_clock_type('cpu')
        GreenletProfiler.start()

    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-e", "--ecdsa-keys", dest="ecdsa",
                      help="Location of ECDSA keys", metavar="KEYS")
    parser.add_option("-k", "--threshold-keys", dest="threshold_keys",
                      help="Location of threshold signature keys", metavar="KEYS")
    parser.add_option("-c", "--threshold-enc", dest="threshold_encs",
                      help="Location of threshold encryption keys", metavar="KEYS")
    parser.add_option("-n", "--number", dest="n",
                      help="Number of parties", metavar="N", type="int")
    parser.add_option("-b", "--propose-size", dest="B",
                      help="Number of transactions to propose", metavar="B", type="int")
    parser.add_option("-t", "--tolerance", dest="t",
                      help="Tolerance of adversaries", metavar="T", type="int")
    parser.add_option("-x", "--transactions", dest="tx",
                      help="Number of transactions proposed by each party", metavar="TX", type="int", default=-1)
    (options, args) = parser.parse_args()
    if (options.ecdsa and options.threshold_keys and options.threshold_encs and options.n and options.t):
        if not options.B:
            options.B = int(math.ceil(options.n * math.log(options.n)))
        if options.tx < 0:
            options.tx = options.B
        client_test_freenet(options.n , options.t, options)
    else:
        parser.error('Please specify the arguments')

