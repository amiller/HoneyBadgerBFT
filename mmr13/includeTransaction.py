__author__ = 'aluex' 

from gevent import Greenlet
from gevent.queue import Queue, Empty
from mmr13 import binary_consensus
from bkr_acs import acs, initBeforeBinaryConsensus
from utils import bcolors, mylog, MonitoredInt, callBackWrap, greenletFunction, greenletPacker
from collections import defaultdict
from ecdsa import SigningKey


class Transaction:
    def __init__(self):
        self.source='Unknown'
        self.target = 'Unknown'
        self.amount = 0
        #### TODO: Define a detailed transaction

    def __repr__(self):
        return bcolors.OKBLUE + "{{Transaction from %s to %s with %d}}" % (self.source, self.target, self.amount) + bcolors.ENDC

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

@greenletFunction
def multiSigBr(pid, N, t, msg, broadcast, receive, outputs):
    # Since all the parties we have are symmetric, so I implement this function for N instances of A-cast as a whole
    # Here msg is a set of transactions
    assert(isinstance(outputs, list))
    for i in outputs:
        assert(isinstance(i, Queue))
    sk = SigningKey.generate() # uses NIST192p
    Pubkeys[pid].put(sk.get_verifying_key())

    def Listener():
        opinions = [defaultdict(lambda: 0) for _ in range(N)]
        signed = [False]*N
        while True:
            sender, msgBundle = receive()
            # mylog("[%d] received msgBundle %s" % (pid, msgBundle))
            vki = Pubkeys[msgBundle[1]].peek()
            if True:  # vki.verify(msgBundle[3], repr(msgBundle[2])):
                # mylog("[%d] Signature passed, msgBundle: %s" % (pid, repr(msgBundle)))
                if msgBundle[0] == 'initial' and not signed[msgBundle[1]]:
                    # Here we should remove the randomness of the signature
                    newBundle = (msgBundle[1], msgBundle[2])
                    broadcast(('echo', pid, newBundle))  #, sk.sign(repr(newBundle))))
                    signed[msgBundle[1]] = True
                elif msgBundle[0] == 'echo':
                    originBundle = msgBundle[2]
                    opinions[originBundle[0]][repr(originBundle[1])] += 1
                    # mylog("[%d] counter for (%d, %s) is now %d" % (pid, originBundle[0],
                    #    repr(originBundle[1]), opinions[originBundle[0]][repr(originBundle[1])]))
                    if opinions[originBundle[0]][repr(originBundle[1])] > (N+t)/2 and not outputs[originBundle[0]].full():
                        outputs[originBundle[0]].put(originBundle[1])

    greenletPacker(Greenlet(Listener), 'multiSigBr.Listener', (pid, N, t, msg, broadcast, receive, outputs)).start()
    broadcast(('initial', pid, msg))  # , sk.sign(repr(msg))))  # Kick Off!

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
            broadcast(('BC', m))
        return _bc_br

    def make_acs_br(i):
        def _acs_br(m):
            broadcast(('ACS', m))
        return _acs_br

    def _listener():
        while True:
            # a = receive()
            # mylog(a, verboseLevel=-1)
            sender, (tag, m) = receive()
            #mylog("[%d] got a msg from %s\n %s" % (pid, repr(sender), repr((tag, m))))
            if tag == 'BC':
                #mylog("[%d] CBChannel put %s" % (pid, repr((sender, m))))

                greenletPacker(Greenlet(CBChannel.put, (sender, m)),
                    'includeTransaction.CBChannel.put', (pid, N, t, setToInclude, broadcast, receive)).start()
            elif tag == 'ACS':
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
        def _callback(commonSet): # now I know player j has succeeded in broadcasting
            #######
            locker.put(commonSet)
        return _callback

    greenletPacker(Greenlet(_listener),
        'includeTransaction._listener', (pid, N, t, setToInclude, broadcast, receive)).start()

    locker = Queue(1)
    includeTransaction.callbackCounter = 0
    monitoredIntList = [MonitoredInt() for _ in range(N)]

    mylog("[%d] Beginning A-Cast on %s" % (pid, repr(setToInclude)))
    greenletPacker(Greenlet(consensusBroadcast, pid, N, t, setToInclude, make_bc_br(pid), CBChannel.get, outputChannel),
        'includeTransaction.consensusBroadcast', (pid, N, t, setToInclude, broadcast, receive)).start()
    mylog("[%d] Beginning ACS" % pid)
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
    mylog("[%d] Honesy party started at %f." % (pid, time.time()), verboseLevel=-1)
    transactionCache = set()
    sessionID = 0
    global finishcount
    while True:
        try:
            # op, msg = controlChannel.get(timeout=HONEST_PARTY_TIMEOUT)
            op, msg = controlChannel.get()
            mylog("[%d] gets some msg %s" % (pid, repr(msg)))
            if op == "IncludeTransaction":
                assert(isinstance(msg, Transaction))
                transactionCache.add(msg)
            elif op == "Halt":
                break
            elif op == "Msg":
                broadcast(eval(msg)) # now the msg is something we mannually send
        except Empty:
            print ">>>"
        finally:
            syncedTXSet = includeTransaction(pid, N, t, transactionCache, broadcast, receive)
            assert(isinstance(syncedTXSet, set))
            transactionCache = transactionCache.difference(syncedTXSet)
            mylog("[%d] synced transactions %s, now cached %s" % (pid, repr(syncedTXSet), repr(transactionCache)), verboseLevel=-1)
            lock.get()
            finishcount += 1
            lock.put(1)
            if finishcount >= N - t:
                sys.exit()
            # raw_input()
        sessionID = sessionID + 1
    mylog("[%d] Now halting..." % (pid))

