__author__ = 'aluex' 

from gevent import Greenlet
from gevent.queue import Queue, Empty
from bkr_acs import acs
from utils import mylog, MonitoredInt, callBackWrap, greenletFunction, \
    greenletPacker, getEncKeys, Transaction, getECDSAKeys, sha1hash, TR_SIZE
from collections import defaultdict
import zfec
import hashlib
from ..threshenc.tpke import encrypt, decrypt
from utils import serializeEnc, deserializeEnc, ENC_SERIALIZED_LENGTH
import random
import itertools
import gevent

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

Pubkeys = defaultdict(lambda : Queue(1) )

class dummyPKI(object):
    @staticmethod
    def get_verifying_key():
        return None

class ECDSASignatureError(Exception):
    pass

import math

def ceil(x):
    return int(math.ceil(x))

def dummyHash(x):  # TODO: replace this guy with good ones
    if isinstance(x, str):
        return int(x.encode('hex'), 16)
    return x + 1

def coolSHA256Hash(x):
    if isinstance(x, int): x = str(x)
    return hashlib.sha256(x).digest()

@greenletFunction
def multiSigBr(pid, N, t, msg, broadcast, receive, outputs, send):
    # Since all the parties we have are symmetric, so I implement this function for N instances of A-cast as a whole
    # Here msg is a set of transactions
    assert(isinstance(outputs, list))
    for i in outputs:
        assert(isinstance(i, Queue))

    keys = getECDSAKeys()
    Threshold = N - 2 * t
    Threshold2 = N - t
    zfecEncoder = zfec.Encoder(Threshold, N)
    zfecDecoder = zfec.Decoder(Threshold, N)

    def merkleTree(strList, someHash = coolSHA256Hash):
        # someHash is a mapping from a int to a int
        treeLength = 2 ** ceil(math.log(len(strList)) / math.log(2))
        mt = [0] * (treeLength * 2)  # find a place to put our leaves
        for i in range(len(strList)):
            mt[i + treeLength] = someHash(strList[i])  # TODO: need to change strList[i] from a string to an integer here.
        for i in range(treeLength - 1, 0, -1):  # 1, 2, 3, ..., treeLength - 1
            # mt[i] = someHash(''.join([chr(ord(a) ^ ord(b)) for a, b in zip(mt[i*2], mt[i*2+1])]))  # XOR is commutative
            mt[i] = someHash(mt[i*2] + mt[i*2+1])  # concat is not commutative
        return mt

    def getMerkleBranch(index, mt):
        res = []
        t = index + (len(mt) >> 1)
        while t > 1:
            res.append(mt[t ^ 1])  # we are picking up the sibling
            t /= 2
        return res

    def merkleVerify(val, rootHash, branch, someHash, index):
        # index has information on whether we are facing a left sibling or a right sibling
        tmp = someHash(val)
        tindex = index
        for br in branch:
            tmp = someHash((tindex & 1) and br + tmp or tmp + br)
            tindex >>= 1
        if tmp != rootHash:
            print "Verification failed with", someHash(val), rootHash, branch, tmp == rootHash
        return tmp == rootHash

    def Listener():
        opinions = [defaultdict(lambda: 0) for _ in range(N)]
        rootHashes = dict()
        readyCounter = [defaultdict(lambda: 0) for _ in range(N)]
        signed = [False]*N
        readySent = [False] * N
        reconstDone = [False] * N
        while True:  # main loop
            sender, msgBundle = receive()
            if msgBundle[0] == 'i' and not signed[sender]:
                if keys[sender].verify(sha1hash(''.join([msgBundle[1][0], msgBundle[1][1], ''.join(msgBundle[1][2])])), msgBundle[2]):
                    assert isinstance(msgBundle[1], tuple)
                    if not merkleVerify(msgBundle[1][0], msgBundle[1][1], msgBundle[1][2], coolSHA256Hash, pid):
                        continue
                    if sender in rootHashes:
                        if rootHashes[sender]!= msgBundle[1][1]:
                            print "Cheating caught, exiting"
                            sys.exit(0)
                    else:
                        rootHashes[sender] = msgBundle[1][1]
                    newBundle = (sender, msgBundle[1][0], msgBundle[1][1], msgBundle[1][2])  # assert each frag has a length of step
                    broadcast(('e', newBundle, keys[pid].sign(
                        sha1hash(''.join([str(newBundle[0]), newBundle[1], newBundle[2], ''.join(newBundle[3])]))
                    )))
                    signed[sender] = True
                else:
                    raise ECDSASignatureError()
            elif msgBundle[0] == 'e':
                if keys[sender].verify(sha1hash(''.join([str(msgBundle[1][0]), msgBundle[1][1], msgBundle[1][2], ''.join(msgBundle[1][3])])), msgBundle[2]):
                    originBundle = msgBundle[1]
                    if not merkleVerify(originBundle[1], originBundle[2], originBundle[3], coolSHA256Hash, sender):
                        continue
                    if originBundle[0] in rootHashes:
                        if rootHashes[originBundle[0]]!= originBundle[2]:
                            print "Cheating caught, exiting"
                            sys.exit(0)
                    else:
                        rootHashes[originBundle[0]] = originBundle[2]
                    opinions[originBundle[0]][sender] = originBundle[1]   # We are going to move this part to kekeketktktktk
                    if len(opinions[originBundle[0]]) >= Threshold2 and not readySent[originBundle[0]]:
                            readySent[originBundle[0]] = True
                            broadcast(('r', originBundle[0], originBundle[2]))  # We are broadcasting its hash
                else:
                    raise ECDSASignatureError()
            elif msgBundle[0] == 'r':
                readyCounter[msgBundle[1]][msgBundle[2]] += 1
                tmp = readyCounter[msgBundle[1]][msgBundle[2]]
                if tmp >= t+1 and not readySent[msgBundle[1]]:
                    readySent[msgBundle[1]] = True
                    broadcast(('r', msgBundle[1], msgBundle[2]))
                if tmp >= Threshold2 and not outputs[msgBundle[1]].full() and \
                        not reconstDone[msgBundle[1]] and len(opinions[msgBundle[1]]) >= Threshold:
                    reconstDone[msgBundle[1]] = True
                    if msgBundle[1] in rootHashes:
                        if rootHashes[msgBundle[1]]!= msgBundle[2]:
                            print "Cheating caught, exiting"
                            sys.exit(0)
                    else:
                        rootHashes[msgBundle[1]] = msgBundle[2]
                    if opinions[msgBundle[1]].values()[0] == '':
                        reconstruction = ['']
                    else:
                        reconstruction = zfecDecoder.decode(opinions[msgBundle[1]].values()[:Threshold],
                                opinions[msgBundle[1]].keys()[:Threshold])  # We only take the first [Threshold] fragments
                    rawbuf = ''.join(reconstruction)
                    buf = rawbuf[:-ord(rawbuf[-1])]
                    # Check root hash
                    step = len(buf) / Threshold + 1 # len(buf) % Threshold == 0 and len(buf) / Threshold or (len(buf) / Threshold + 1)
                    assert step * Threshold - len(buf) < 256  # assumption
                    buf_ = buf.ljust(step * Threshold - 1, '\xFF') + chr(step * Threshold - len(buf))
                    fragList = [buf_[i*step : (i+1)*step] for i in range(Threshold)]
                    encodedFragList = zfecEncoder.encode(fragList)
                    mt = merkleTree(encodedFragList, coolSHA256Hash)
                    assert rootHashes[msgBundle[1]] == mt[1]  # full binary tree
                    if outputs[msgBundle[1]].empty():
                        outputs[msgBundle[1]].put(buf)

    greenletPacker(Greenlet(Listener), 'multiSigBr.Listener', (pid, N, t, msg, broadcast, receive, outputs)).start()
    buf = msg  # We already assumed the proposals are byte strings

    step = len(buf) / Threshold + 1 # len(buf) % Threshold == 0 and len(buf) / Threshold or (len(buf) / Threshold + 1)
    assert step * Threshold - len(buf) < 256  # assumption
    buf = buf.ljust(step * Threshold - 1, '\xFF') + chr(step * Threshold - len(buf))
    fragList = [buf[i*step : (i+1)*step] for i in range(Threshold)]
    encodedFragList = zfecEncoder.encode(fragList)
    mt = merkleTree(encodedFragList, coolSHA256Hash)
    rootHash = mt[1]  # full binary tree
    for i in range(N):
        mb = getMerkleBranch(i, mt)  # notice that index starts from 1 and pid starts from 0
        newBundle = (encodedFragList[i], rootHash, mb)
        send(i, ('i', newBundle, keys[pid].sign(sha1hash(''.join([newBundle[0], newBundle[1], ''.join(newBundle[2])])))))

@greenletFunction
def consensusBroadcast(pid, N, t, msg, broadcast, receive, outputs, send, method=multiSigBr):
    return method(pid, N, t, msg, broadcast, receive, outputs, send)


def union(listOfTXSet):
    result = set() # Informal Union: actually we don't know how it compares ...
    for s in listOfTXSet:
        result = result.union(s)
    return result

# tx is the transaction we are going to include
@greenletFunction
def includeTransaction(pid, N, t, setToInclude, broadcast, receive, send):
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

    def make_bc_send(i):
        def _layer_send(j, m):
            send(j, ('B', m))
        return _layer_send

    def _listener():
        while True:
            sender, (tag, m) = receive()
            if tag == 'B':
                greenletPacker(Greenlet(CBChannel.put, (sender, m)),
                    'includeTransaction.CBChannel.put', (pid, N, t, setToInclude, broadcast, receive)).start()
            elif tag == 'A':
                greenletPacker(Greenlet(ACSChannel.put,
                    (sender, m)
                ), 'includeTransaction.ACSChannel.put', (pid, N, t, setToInclude, broadcast, receive)).start()

    outputChannel = [Queue(1) for _ in range(N)]

    def outputCallBack(i):
        TXSet[i] = outputChannel[i].get()
        monitoredIntList[i].data = 1

    for i in range(N):
        greenletPacker(Greenlet(outputCallBack, i),
            'includeTransaction.outputCallBack', (pid, N, t, setToInclude, broadcast, receive)).start()

    def callbackFactoryACS():
        def _callback(commonSet):  # now I know player j has succeeded in broadcasting
            locker.put(commonSet)
        return _callback

    greenletPacker(Greenlet(_listener),
        'includeTransaction._listener', (pid, N, t, setToInclude, broadcast, receive)).start()

    locker = Queue(1)
    includeTransaction.callbackCounter = 0
    monitoredIntList = [MonitoredInt() for _ in range(N)]

    greenletPacker(Greenlet(consensusBroadcast, pid, N, t, setToInclude, make_bc_br(pid), CBChannel.get, outputChannel, make_bc_send(pid)),
        'includeTransaction.consensusBroadcast', (pid, N, t, setToInclude, broadcast, receive)).start()
    greenletPacker(Greenlet(callBackWrap(acs, callbackFactoryACS()), pid, N, t, monitoredIntList, make_acs_br(pid), ACSChannel.get),
        'includeTransaction.callBackWrap(acs, callbackFactoryACS())', (pid, N, t, setToInclude, broadcast, receive)).start()

    commonSet = locker.get()
    return commonSet, TXSet

HONEST_PARTY_TIMEOUT = 1

import time, sys
lock = Queue()
finishcount = 0
lock.put(1)

@greenletFunction
def honestParty(pid, N, t, controlChannel, broadcast, receive, send, B = -1):
    # RequestChannel is called by the client and it is the client's duty to broadcast the tx it wants to include
    if B < 0:
        B = int(math.ceil(N * math.log(N)))
    transactionCache = []
    finishedTx = set()
    proposals = []
    receivedProposals = False
    commonSet = []
    locks = defaultdict(lambda : Queue(1))
    doneCombination = defaultdict(lambda : False)
    ENC_THRESHOLD = N - 2 * t
    global finishcount
    encPK, encSKs = getEncKeys()
    encCounter = defaultdict(lambda : {})
    includeTransactionChannel = Queue()

    def probe(i):
        if len(encCounter[i]) >= ENC_THRESHOLD and receivedProposals and not locks[i].full() and not doneCombination[i]:  # by == this part only executes once.
            oriM = encPK.combine_shares(deserializeEnc(proposals[i][:ENC_SERIALIZED_LENGTH]),
                                        dict(itertools.islice(encCounter[i].iteritems(), ENC_THRESHOLD))
                                        )
            doneCombination[i] = True
            locks[i].put(oriM)

    def listener():
        while True:
            sender, msgBundle = receive()
            if msgBundle[0] == 'O':
                encCounter[msgBundle[1]][sender] = msgBundle[2]
                probe(msgBundle[1])
            else:
                includeTransactionChannel.put((sender, msgBundle))  # redirect to includeTransaction

    Greenlet(listener).start()

    while True:
            op, msg = controlChannel.get()
            if op == "IncludeTransaction":
                if isinstance(msg, Transaction):
                    # transactionCache.add(msg)
                    transactionCache.append(msg)
                elif isinstance(msg, set):
                    for tx in msg:
                        transactionCache.append(tx)
                elif isinstance(msg, list):
                    transactionCache.extend(msg)
            elif op == "Halt":
                break
            elif op == "Msg":
                broadcast(eval(msg))  # now the msg is something we mannually send
            mylog("timestampB (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            if len(transactionCache) < B:  # Let's wait for many transactions. : )
                time.sleep(0.5)
                print "Not enough transactions", len(transactionCache)
                continue

            oldest_B = transactionCache[:B]
            selected_B = random.sample(oldest_B, min(B/N, len(oldest_B)))
            print "[%d] proposing %d transactions" % (pid, min(B/N, len(oldest_B)))
            aesKey = random._urandom(32)  #
            encrypted_B = encrypt(aesKey, ''.join(selected_B))
            encryptedAESKey = encPK.encrypt(aesKey)
            proposal = serializeEnc(encryptedAESKey) + encrypted_B
            mylog("timestampIB (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            commonSet, proposals = includeTransaction(pid, N, t, proposal, broadcast, includeTransactionChannel.get, send)
            mylog("timestampIE (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            receivedProposals = True
            for i in range(N):
                probe(i)
            for i, c in enumerate(commonSet):  # stx is the same for every party
                if c:
                    share = encSKs[pid].decrypt_share(deserializeEnc(proposals[i][:ENC_SERIALIZED_LENGTH]))
                    broadcast(('O', i, share))
            mylog("timestampIE2 (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            recoveredSyncedTxList = []
            def prepareTx(i):
                rec = locks[i].get()
                encodedTxSet = decrypt(rec, proposals[i][ENC_SERIALIZED_LENGTH:])
                assert len(encodedTxSet) % TR_SIZE == 0
                recoveredSyncedTx = [encodedTxSet[i:i+TR_SIZE] for i in range(0, len(encodedTxSet), TR_SIZE)]
                recoveredSyncedTxList.append(recoveredSyncedTx)
            thList = []
            for i, c in enumerate(commonSet):  # stx is the same for every party
                if c:
                    s = Greenlet(prepareTx, i)
                    thList.append(s)
                    s.start()
            gevent.joinall(thList)
            mylog("timestampE (%d, %lf)" % (pid, time.time()), verboseLevel=-2)
            for rtx in recoveredSyncedTxList:
                finishedTx.update(set(rtx))

            mylog("[%d] %d distinct tx synced and %d tx left in the pool." % (pid, len(finishedTx), len(transactionCache) - len(finishedTx)), verboseLevel=-2)
            lock.get()
            finishcount += 1
            lock.put(1)
            if finishcount >= N - t:  # convenient for local experiments
                sys.exit()
    mylog("[%d] Now halting..." % (pid))

