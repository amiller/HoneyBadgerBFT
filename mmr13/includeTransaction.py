__author__ = 'aluex' 

from gevent import Greenlet
from gevent.queue import Queue, Empty
from mmr13 import binary_consensus
from bkr_acs import acs, initBeforeBinaryConsensus
from utils import bcolors, mylog, MonitoredInt, callBackWrap, greenletFunction, \
    greenletPacker, PK, SKs, Transaction, getECDSAKeys, sha1hash, setHash, finishTransactionLeap, encodeTransaction, constructTransactionFromRepr, TR_SIZE
from collections import defaultdict
import zfec
import socket
from io import BytesIO
# from ecdsa import SigningKey
import struct


def calcSum(dd):
    return sum([x for _, x in dd.items()])

def calcMajority(dd):
    maxvalue = -1
    maxkey = dd.values()[0]
    for key, value in dd.items():
        if value > maxvalue:
            maxvalue = value
            maxkey = key
    return maxkey


comment = '''def bracha_85(pid, N, t, msg, broadcast, send, receive, outputs): # TODO: May not work!!!
    assert(isinstance(outputs, list))
    for i in outputs:
        assert(isinstance(i, Queue))
    assert(isinstance(msg, str))
    msg_count = defaultdict(lambda _: 0)
    echo_count = [defaultdict(lambda _: 0)]*N
    phaseno = 0
    msgDict = {}
    broadcast(('initial', pid, msg, phaseno))
    while sum(msg_count) < N - t:
        msg = receive()
        if not (msg[0], msg[1], msg[3]) in msgDict:
            msgDict[(msg[0], msg[1], msg[3])] = 1
            if msg[0] == 'initial':
                broadcast(('echo', msg[1], msg[2], msg[3]))
            elif msg[1] == 'echo' and msg[3] == phaseno:
                echo_count[msg[1]][msg[2]] = echo_count[msg[1]][msg[2]] + 1
                if echo_count[msg[1]][msg[2]] == (N + t)/2 + 1:
                    msg_count[msg[2]] = msg_count[msg[2]] + 1
            elif msg[1] == 'echo' and msg[3] > phaseno:
                send(pid, msg) # return the msg to the queue until we are at the same phaseno
        value = calcMajority(msg_count)
        if msg_count[value] > (N+t)/2:
            return value # now we can decide
        phaseno = phaseno + 1'''

Pubkeys = defaultdict(lambda : Queue(1) )

class dummyPKI(object):
    @staticmethod
    def get_verifying_key():
        return None

class ECDSASignatureError(Exception):
    pass

import math

def ceil(x):
    #assert isinstance(x, float)
    #if int(x) != x:
    #    return int(x)+1
    #return int(x)
    return int(math.ceil(x))

@greenletFunction
def multiSigBr(pid, N, t, msg, broadcast, receive, outputs):
    # Since all the parties we have are symmetric, so I implement this function for N instances of A-cast as a whole
    # Here msg is a set of transactions
    assert(isinstance(outputs, list))
    for i in outputs:
        assert(isinstance(i, Queue))
    #sk = dummyPKI() # SigningKey.generate() # uses NIST192p
    #Pubkeys[pid].put(sk.get_verifying_key())

    keys = getECDSAKeys()
    Threshold = ceil((N-t+1)/2.0)
    Threshold2 = ceil((N+t+1)/2.0)

    zfecEncoder = zfec.Encoder(Threshold, N)
    zfecDecoder = zfec.Decoder(Threshold, N)

    def Listener():
        opinions = [defaultdict(lambda: 0) for _ in range(N)]
        readyCounter = [defaultdict(lambda: 0) for _ in range(N)]
        signed = [False]*N
        readySent = [False] * N
        reconstDone = [False] * N
        reconsLocker = [Queue() for _ in range(N)]
        finalTrigger = [Queue() for _ in range(N)]
        def final(i):  # only one time
            buf = reconsLocker[i].get()
            finalTrigger[i].get()
            # mylog("[%d] finished acast on msg from %d." % (pid, i), verboseLevel=-2)
            outputs[i].put([constructTransactionFromRepr(buf[i:i+TR_SIZE]) for i in range(0, len(buf), TR_SIZE)])
        for i in range(N):
            Greenlet(final, i).start()
        while True:
            sender, msgBundle = receive()
            #mylog("[%d] multiSigBr received msgBundle %s" % (pid, msgBundle), verboseLevel=-1)
            # vki = Pubkeys[msgBundle[1]].peek()
            if msgBundle[0] == 'i' and not signed[msgBundle[1]]:
                # if keys[msgBundle[1]].verify(sha1hash(hex(setHash(msgBundle[2]))), msgBundle[3]):
                if keys[msgBundle[1]].verify(sha1hash(msgBundle[2]), msgBundle[3]):
                    # Here we should remove the randomness of the signature
                    # assert isinstance(msgBundle[2], set)
                    assert isinstance(msgBundle[2], str)
                    buf = msgBundle[2] # now it is a string  # ''.join([encodeTransaction(tr) for tr in msgBundle[2]])
                    #print sender, 'sent', len(buf), repr(buf)
                    step = len(buf) % Threshold == 0 and len(buf) / Threshold or (len(buf) / Threshold + 1)
                    fragList = [buf[i*step:(i+1)*step] for i in range(Threshold)]
                    if len(fragList[-1]) < step:
                        fragList[-1] = fragList[-1] + '\xFF' * (step - len(fragList[-1]))  # padding
                    #print sender, 'fragList', fragList
                    #print sender, 'encoded', zfecEncoder.encode(fragList)
                    newBundle = (msgBundle[1], zfecEncoder.encode(fragList)[pid])
                    #newBundle = (msgBundle[1], msgBundle[2])
                    #mylog("[%d] we are to echo msgBundle: %s" % (pid, repr(msgBundle)), verboseLevel=-1)
                    #mylog("[%d] and now signed is %s" % (pid, repr(signed)), verboseLevel=-1)
                    #broadcast(('e', pid, newBundle, keys[pid].sign(sha1hash(hex((newBundle[0]+37)*setHash(newBundle[1]))))))
                    Greenlet(broadcast, ('e', pid, newBundle, keys[pid].sign(
                        sha1hash(repr(newBundle))
                    ))).start()
                    #broadcast(('e', pid, newBundle, keys[pid].sign(
                    #    sha1hash(repr(newBundle))
                    #)))
                    signed[msgBundle[1]] = True
                else:
                    raise ECDSASignatureError()
            elif msgBundle[0] == 'e':
                #if keys[msgBundle[1]].verify(sha1hash(hex((msgBundle[2][0]+37)*setHash(msgBundle[2][1]))), msgBundle[3]):
                if keys[msgBundle[1]].verify(sha1hash(repr(msgBundle[2])), msgBundle[3]):
                    originBundle = msgBundle[2]
                    opinions[originBundle[0]][sender] = originBundle[1]
                    # mylog("[%d] got %d echos for %d" % (pid, len(opinions[originBundle[0]]), originBundle[0]),
                    #      verboseLevel=-2)
                    # opinions[originBundle[0]][repr(originBundle[1])] += 1
                    # mylog("[%d] counter for (%d, %s) is now %d" % (pid, originBundle[0],
                    #    repr(originBundle[1]), opinions[originBundle[0]][repr(originBundle[1])]))
                    # if opinions[originBundle[0]][repr(originBundle[1])] > (N+t)/2 and not outputs[originBundle[0]].full():
                    if len(opinions[originBundle[0]]) >= Threshold2 and not reconstDone[originBundle[0]]:
                        reconstDone[originBundle[0]] = True
                        # mylog("[%d] got %d echos for %d to reconstruction" % (pid, len(opinions[originBundle[0]]), originBundle[0]),
                        #  verboseLevel=-2)
                        reconstruction = zfecDecoder.decode(opinions[originBundle[0]].values()[:Threshold],
                                opinions[originBundle[0]].keys()[:Threshold])  # We only take the first [Threshold] fragments
                        # assert len(reconstruction) == Threshold
                        buf = ''.join(reconstruction).rstrip('\xFF')
                        #print opinions[originBundle[0]].values()[:Threshold]
                        #print opinions[originBundle[0]].keys()[:Threshold]
                        #print originBundle[0], '->', sender, len(buf), repr(buf)
                        assert len(buf) % TR_SIZE == 0
                        if reconsLocker[originBundle[0]].empty():
                            reconsLocker[originBundle[0]].put(buf)
                        # mylog("[%d] put reconsLocker for %d" % (pid, originBundle[0]), verboseLevel=-2)
                        if not readySent[originBundle[0]]:
                            readySent[originBundle[0]] = True
                            Greenlet(broadcast, ('r', originBundle[0], sha1hash(buf))).start()
                        # broadcast(('r', originBundle[0], sha1hash(buf)))  # to clarify which this ready msg refers to
                else:
                    raise ECDSASignatureError()
            elif msgBundle[0] == 'r':
                readyCounter[msgBundle[1]][msgBundle[2]] += 1
                tmp = readyCounter[msgBundle[1]][msgBundle[2]]
                # print pid, msgBundle[1], tmp
                if tmp >= t+1 and not readySent[msgBundle[1]]:
                    readySent[msgBundle[1]] = True
                    Greenlet(broadcast, ('r', msgBundle[1], msgBundle[2])).start()
                    # broadcast(('r', msgBundle[1], msgBundle[2]))  # relay the msg
                if tmp >= 2*t+1 and not outputs[msgBundle[1]].full() and finalTrigger[msgBundle[1]].empty():
                    finalTrigger[msgBundle[1]].put(1)
                    # mylog("[%d] put finalTrigger for %d" % (pid, msgBundle[1]), verboseLevel=-2)

    greenletPacker(Greenlet(Listener), 'multiSigBr.Listener', (pid, N, t, msg, broadcast, receive, outputs)).start()
    encodedMsg = ''.join([encodeTransaction(tr) for tr in msg])
    # broadcast(('i', pid, msg, keys[pid].sign(sha1hash(hex(setHash(msg))))))  # Kick Off!
    broadcast(('i', pid, encodedMsg, keys[pid].sign(sha1hash(encodedMsg))))  # Kick Off!

@greenletFunction
def consensusBroadcast(pid, N, t, msg, broadcast, receive, outputs, method=multiSigBr):
    return method(pid, N, t, msg, broadcast, receive, outputs)


def union(listOfTXSet):
    result = set() # Informal Union: actually we don't know how it compares ...
    for s in listOfTXSet:
        result = result.union(s)
    mylog("Union on %s gives %s" % (repr(listOfTXSet), repr(result)))
    return result

# tx is the transaction we are going to include
@greenletFunction
def includeTransaction(pid, N, t, setToInclude, broadcast, receive):

    for tx in setToInclude:
        assert(isinstance(tx, Transaction))

    CBChannel = Queue()
    ACSChannel = Queue()
    TXSet = [{} for _ in range(N)]

    def make_bc_br(i):
        def _bc_br(m):
            broadcast(('B', m))
        return _bc_br

    def make_acs_br(i):
        def _acs_br(m):
            broadcast(('A', m))
        return _acs_br

    def _listener():
        while True:
            # a = receive()
            # mylog(a, verboseLevel=-1)
            sender, (tag, m) = receive()
            # mylog("[%d] got a msg from %s\n %s" % (pid, repr(sender), repr((tag, m))), verboseLevel=-1)
            if tag == 'B':
                #mylog("[%d] CBChannel put %s" % (pid, repr((sender, m))))

                greenletPacker(Greenlet(CBChannel.put, (sender, m)),
                    'includeTransaction.CBChannel.put', (pid, N, t, setToInclude, broadcast, receive)).start()
            elif tag == 'A':
                greenletPacker(Greenlet(ACSChannel.put,
                    (sender, m)
                ), 'includeTransaction.ACSChannel.put', (pid, N, t, setToInclude, broadcast, receive)).start()

    outputChannel = [Queue(1) for _ in range(N)]

    def outputCallBack(i):
        TXSet[i] = outputChannel[i].get()
        mylog(bcolors.OKGREEN + "[%d] get output(%d) as TXSet: %s" % (pid, i, repr(TXSet[i])) + bcolors.ENDC)
        monitoredIntList[i].data = 1

    for i in range(N):
        greenletPacker(Greenlet(outputCallBack, i),
            'includeTransaction.outputCallBack', (pid, N, t, setToInclude, broadcast, receive)).start()

    def callbackFactoryACS():
        def _callback(commonSet):  # now I know player j has succeeded in broadcasting
            #######
            locker.put(commonSet)
        return _callback

    greenletPacker(Greenlet(_listener),
        'includeTransaction._listener', (pid, N, t, setToInclude, broadcast, receive)).start()

    locker = Queue(1)
    includeTransaction.callbackCounter = 0
    monitoredIntList = [MonitoredInt() for _ in range(N)]

    mylog("[%d] Beginning A-Cast on %s" % (pid, repr(setToInclude)), verboseLevel=-1)
    greenletPacker(Greenlet(consensusBroadcast, pid, N, t, setToInclude, make_bc_br(pid), CBChannel.get, outputChannel),
        'includeTransaction.consensusBroadcast', (pid, N, t, setToInclude, broadcast, receive)).start()
    mylog("[%d] Beginning ACS" % pid, verboseLevel=-1)
    greenletPacker(Greenlet(callBackWrap(acs, callbackFactoryACS()), pid, N, t, monitoredIntList, make_acs_br(pid), ACSChannel.get),
        'includeTransaction.callBackWrap(acs, callbackFactoryACS())', (pid, N, t, setToInclude, broadcast, receive)).start()

    commonSet = locker.get()
    subTXSet = [TXSet[x] for x in range(N) if commonSet[x] == 1]

    return union(subTXSet)

HONEST_PARTY_TIMEOUT = 1

import time, sys
lock = Queue()
finishcount = 0
lock.put(1)

@greenletFunction
def honestParty(pid, N, t, controlChannel, broadcast, receive):
    # RequestChannel is called by the client and it is the client's duty to broadcast the tx it wants to include
    #sock = socket.create_connection((sys.argv[4], 51234))
    transactionCache = set()
    sessionID = 0
    global finishcount
    while True:
        try:
            # op, msg = controlChannel.get(timeout=HONEST_PARTY_TIMEOUT)
            op, msg = controlChannel.get()
            mylog("[%d] gets some msg %s" % (pid, repr(msg)))
            if op == "IncludeTransaction":
                if isinstance(msg, Transaction):
                    transactionCache.add(msg)
                elif isinstance(msg, set):
                    transactionCache.update(msg)
                print 'got', len(transactionCache), 'TXs'
            elif op == "Halt":
                break
            elif op == "Msg":
                broadcast(eval(msg))  # now the msg is something we mannually send
        except Empty:
            print ">>>"
        finally:
            mylog("timestampB (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            syncedTXSet = includeTransaction(pid, N, t, transactionCache, broadcast, receive)
            assert(isinstance(syncedTXSet, set))
            transactionCache = transactionCache.difference(syncedTXSet)
            #mylog("[%d] synced transactions %s, now cached %s" % (pid, repr(syncedTXSet), repr(transactionCache)), verboseLevel = -1)
            mylog("[%d] synced transactions." % pid, verboseLevel = -2)
            mylog("timestampE (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            lock.get()
            finishcount += 1
            lock.put(1)
            # if len(sys.argv) > 4: # we have a client parameter
            #     sock.sendall("[%d] synced transactions %s, now cached %s" % (pid, repr(syncedTXSet), repr(transactionCache)))
            if finishcount >= N - t:  # convenient for local experiments
                sys.exit()
                #raise finishTransactionLeap()  # long-jump
                # sys.exit()
            # raw_input()
        sessionID = sessionID + 1
    mylog("[%d] Now halting..." % (pid))

