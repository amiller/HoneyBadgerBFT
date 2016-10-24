#!/usr/bin/python
__author__ = 'aluex'
from gevent import monkey
monkey.patch_all()

from gevent.queue import *
from gevent import Greenlet
from ..core.utils import bcolors, mylog, initiateThresholdSig
from ..core.includeTransaction import honestParty, Transaction
from collections import defaultdict
from ..core.bkr_acs import initBeforeBinaryConsensus
import gevent
import os
from gevent.server import StreamServer
from ..core.utils import ACSException, checkExceptionPerGreenlet, getSignatureCost, encodeTransaction, getKeys, \
    deepEncode, deepDecode, randomTransaction, initiateECDSAKeys, initiateThresholdEnc, finishTransactionLeap
import time
import socks
import struct
from os.path import expanduser
from ..commoncoin.boldyreva_gipc import initialize as initializeGIPC

# USE_DEEP_ENCODE = True # It must be encoded
QUIET_MODE = False  # we are logging the messages

TOR_SOCKSPORT = range(9050, 9150)

def goodread(f, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        buf.append(f.read(ltmp))
        ltmp -= len(buf[-1])
    return ''.join(buf)

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue()
    def _handle(socket, address):
        f = socket.makefile()
        while True:
            msglength, = struct.unpack('<I', goodread(f, 4))
            line = goodread(f, msglength)
            obj = decode(line)
            q.put(obj[1:])

    server = StreamServer(('0.0.0.0', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, party):
    mylog('Trying to connect to %s for party %d' % (repr((hostname, port)), party), verboseLevel=-2)
    retry = True
    s = socks.socksocket()
    while retry:
      try:
        s = socks.socksocket()
        s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", TOR_SOCKSPORT[party], True)
        s.connect((hostname, port))
        retry = False
      except Exception, e:  # socks.SOCKS5Error:  # still no idea why socks over tor would always generate this error
        retry = True
        gevent.sleep(1)
        s.close()
        mylog('retrying (%s, %d) caused by %s...' % (hostname, port, str(e)) , verboseLevel=-2)
    q = Queue()
    def _handle():
        while True:
            obj = q.get()
            content = encode(obj)
            s.sendall(struct.pack('<I', len(content)) + content)
                
    gtemp = Greenlet(_handle)
    gtemp.parent_args = (hostname, port, party)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

BASE_PORT = 49500

TOR_MAPPING_LIST, TOR_MAPPINGS = None, None

mylog("[INIT] TOR_MAPPINGS: %s" % repr(TOR_MAPPINGS))


def initTorConfiguration(hosts):
    global TOR_MAPPINGS, TOR_MAPPING_LIST
    TOR_MAPPING_LIST = open(expanduser(hosts),'r').read().strip().split('\n')
    TOR_MAPPINGS = [(host, BASE_PORT+i) for i, host in enumerate(TOR_MAPPING_LIST)]

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

msgCounter = 0
totalMessageSize = 0
starting_time = defaultdict(lambda: 0.0)
ending_time = defaultdict(lambda: 0.0)
msgSize = defaultdict(lambda: 0)
msgFrom = defaultdict(lambda: 0)
msgTo = defaultdict(lambda: 0)
msgContent = defaultdict(lambda: '')
msgTypeCounter = [[0, 0] for _ in range(8)]
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

def encode(m):  # TODO
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())
    result = deepEncode(msgCounter, m)
    if m[0] == m[1]:
        msgSize[msgCounter] = 0
    else:
        msgSize[msgCounter] = len(result)
    msgFrom[msgCounter] = m[1]
    msgTo[msgCounter] = m[0]
    msgContent[msgCounter] = m
    return result

def decode(s):  # TODO
    result = deepDecode(s, msgTypeCounter)
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
    initTorConfiguration(options.hosts)
    initiateThresholdSig(open(options.threshold_keys, 'r').read())
    initiateECDSAKeys(open(options.ecdsa, 'r').read())
    initiateThresholdEnc(open(options.threshold_encs, 'r').read())
    initializeGIPC(getKeys()[0])
    global logGreenlet
    logGreenlet = Greenlet(logWriter, open('msglog.TorMultiple', 'w'))
    logGreenlet.parent_args = (N, t)
    logGreenlet.name = 'client_test_freenet.logWriter'
    logGreenlet.start()

    servers = []
    for i in range(N):
        _, port = TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        chans = []
        # First establish N connections (including a self connection)
        for j in range(N):
            host, port = TOR_MAPPINGS[j]
            chans.append(connect_to_channel(host, port, i))
        def _broadcast(v):
            for j in range(N):
                if j != i:
                    chans[j].put((j, i, v))  # from i to j
            servers[i].put((i, v))  # this is what the reader see. We are doing a shortcut.
        def _delivery(j, v):
            chans[j].put((j, i, v))
        return _broadcast, _delivery

    gevent.sleep(2)
    print 'servers started'

    # while True:
    if True:  # We only test for once
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        bcList = dict()
        sdList = dict()
        tList = []
        transactionSet = set([encodeTransaction(randomTransaction()) for trC in range(int(options.tx))])  # we are using the same one
        def _makeBroadcast(x):
            bc, sd = makeBroadcast(x)
            bcList[x] = bc
            sdList[x] = sd
        for i in range(N):
            tmp_t = Greenlet(_makeBroadcast, i)
            tmp_t.parent_args = (N, t)
            tmp_t.name = 'client_test_freenet._makeBroadcast(%d)' % i
            tmp_t.start()
            tList.append(tmp_t)
        gevent.joinall(tList)
        for i in range(N):
            recv = servers[i].get
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bcList[i], recv, sdList[i], options.B)
            th.parent_args = (N, t)
            th.name = 'client_test_freenet.honestParty(%d)' % i
            th.start()
            mylog('Summoned party %i at time %f' % (i, time.time()), verboseLevel=-1)
            ts.append(th)
        for i in range(N):
            controlChannels[i].put(('IncludeTransaction', transactionSet))

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
            # checkExceptionPerGreenlet()
            # print getSignatureCost()
            pass
        except gevent.hub.LoopExit:  # Manual fix for early stop
            while True:
                gevent.sleep(1)
            checkExceptionPerGreenlet()
        finally:
            print "Concensus Finished"

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
    # print "Started"
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
    parser.add_option("-s", "--hosts", dest="hosts",
                      help="Host list file", metavar="HOSTS", default="~/hosts")
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
            options.tx = options.B  # right B transactions
        client_test_freenet(options.n , options.t, options)
    else:
        parser.error('Please specify the arguments')

