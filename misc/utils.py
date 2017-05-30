from gevent import monkey
monkey.patch_all()

from gevent.queue import Queue
from gevent import Greenlet
import random
import hashlib
import gc
import traceback
import cPickle as pickle
import struct
from ..ecdsa.ecdsa_ssl import KEY
import os
from ..commoncoin import boldyreva as boldyreva
from ..threshenc.tpke import serialize, deserialize0, deserialize1, deserialize2, TPKEPublicKey, TPKEPrivateKey, group

from io import BytesIO

nameList = open(os.path.dirname(os.path.abspath(__file__)) + '/../test/names.txt','r').read().strip().split('\n')

TR_SIZE = 250
SHA_LENGTH = 32
PAIRING_SERIALIZED_0 = 28
PAIRING_SERIALIZED_1 = 65 # 29  # 65
PAIRING_SERIALIZED_2 = 85
BOLDYREVA_SERIALIZED_1 = 29
CURVE_LENGTH = 32

ENC_SERIALIZED_LENGTH = PAIRING_SERIALIZED_1 * 2 + CURVE_LENGTH

verbose = -2
goodseed = random.randint(1, 10000)
myRandom = random.Random(goodseed)

signatureCost = 0

def callBackWrap(func, callback):
    def _callBackWrap(*args, **kargs):
        result = func(*args, **kargs)
        callback(result)

    return _callBackWrap

PK, SKs = None, None
encPK, encSKs = None, None

ecdsa_key_list = []

from Crypto.Hash import SHA256
sha1hash = lambda x: SHA256.new(x).digest()

import sys
import os
sys.path.append(os.path.abspath('../commoncoin'))


class Transaction:  # assume amout is in term of short
    def __init__(self):
        self.source='Unknown'
        self.target = 'Unknown'
        self.amount = 0
        #### TODO: Define a detailed transaction

    def __repr__(self):
        return bcolors.OKBLUE + "{{Transaction from %s to %s with %d}}" % (self.source, self.target, self.amount) + bcolors.ENDC

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.source == other.source and self.target == other.target and self.amount == other.amount
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.source) ^ hash(self.target) ^ hash(self.amount)


def randomTransaction(randomGenerator=random):
    tx = Transaction()
    tx.source = randomGenerator.choice(nameList)
    tx.target = randomGenerator.choice(nameList)
    tx.amount = randomGenerator.randint(1, 32767)  # not 0
    return tx

def randomTransactionStr():
    return repr(randomTransaction())

class deepEncodeException(Exception):
    pass

class deepDecodeException(Exception):
    pass

class finishTransactionLeap(Exception):
    pass

def encodeTransactionEnc(trE):
    # print 'encTr', trE
    return ''.join(trE).ljust(TR_SIZE, ' ')

LONG_RND_STRING = ''
bio = None

def long_string(n, seed='testbadger1'):
    from subprocess import check_output
    import os
    FNULL = open(os.devnull, 'w')
    string = check_output('openssl enc -aes-256-ctr -pass pass:%s -nosalt < /dev/zero | head -c %d' % (seed,n), shell=True, close_fds=True, stderr=FNULL)
    assert len(string) == n
    return string

def getSomeRandomBytes(length, rnd=random):
    maxL = len(LONG_RND_STRING) - 1 - length
    startP = rnd.randint(0, maxL)
    return LONG_RND_STRING[startP:startP+length]

# assumptions: amount of the money transferred can be expressed in 2 bytes.
def encodeTransaction(tr, randomGenerator=None, length=TR_SIZE):
    sourceInd = nameList.index(tr.source)
    targetInd = nameList.index(tr.target)
    if randomGenerator:
        return struct.pack(
        '<BBH', sourceInd, targetInd, tr.amount
    ) + getSomeRandomBytes(TR_SIZE - 5, randomGenerator)  + '\x90'
    return struct.pack(
        '<BBH', sourceInd, targetInd, tr.amount
    ) + os.urandom(TR_SIZE - 5) + '\x90'


# assumptions:
# + mc can be expressed in 4 bytes.
# + party index can be expressed in 1 byte.
# + round index can be expressed in 2 bytes.
# + transactions with ammount > 0 [THIS IS IMPORTANT for separation]
# + transaction set fragments is less than 2^32 bytes
# + the length of Merkle Branch is no more than a byte (256).

def deepEncode(mc, m):
    buf = BytesIO()
    buf.write(struct.pack('<I', mc))
    f, t, bundle = m
    buf.write(struct.pack('BB', f, t))
    if bundle[0] == 'O':
        tag, id, share = bundle
        buf.write('\x07')
        buf.write(struct.pack('B', id))
        buf.write(serialize(share))
    else:
        (tag, c) = bundle
        # totally we have 4 msg types
        if c[0]=='i':
            buf.write('\x01')
            t2, (s, rh, mb), sig = c
            buf.write(struct.pack('<IB', len(s), len(mb)))  # here we write the # of tx instead of # of bytes
            buf.write(s)  # here we assume s is an encoded set of transaction
            buf.write(rh)
            for br in mb:
                buf.write(br)  ## still SHA_LENGTH bytes each
            buf.write(sig)
        elif c[0]=='e':
            # print c
            buf.write('\x02')
            t2, (p2, s, rh, mb), sig = c  # rh is the root hash and mb is the merkle branch
            buf.write(struct.pack('<BIB', p2, len(s), len(mb)))
            buf.write(s)  ## here we already have them encoded
            buf.write(rh)  ## it's SHA_LENGTH bytes
            for br in mb:
                buf.write(br)  ## still SHA_LENGTH bytes each
            buf.write(sig)
        elif c[0]=='r':
            buf.write('\x06')
            t2, p1, hm = c
            buf.write(struct.pack('B', p1))
            buf.write(hm)
        else:
            p1, (t2, m2) = c
            if t2 == 'B':
                buf.write('\x03')
            elif t2 == 'A':
                buf.write('\x04')
            elif t2 == 'C':
                buf.write('\x05')
                r, sig = m2
                buf.write(struct.pack('<BH', p1, r))
                buf.write(boldyreva.serialize(sig))
                buf.seek(0)
                return buf.read()
            else:
                raise deepEncodeException()
            (p2, p3) = m2
            buf.write(struct.pack('BBB', p1, p2, p3))
    buf.seek(0)
    return buf.read()

def serializeEnc(C):
    assert len(serialize(C[0]))==PAIRING_SERIALIZED_1
    assert len(C[1]) == CURVE_LENGTH
    assert len(serialize(C[2]))==PAIRING_SERIALIZED_1
    return ''.join((serialize(C[0]), C[1], serialize(C[2])))

def deserializeEnc(r):
    return (deserialize1(r[:PAIRING_SERIALIZED_1]), r[PAIRING_SERIALIZED_1:PAIRING_SERIALIZED_1+CURVE_LENGTH],
            deserialize1(r[PAIRING_SERIALIZED_1+CURVE_LENGTH:PAIRING_SERIALIZED_1+PAIRING_SERIALIZED_1+CURVE_LENGTH]))

def constructTransactionFromRepr(r):
    sourceInd, targetInd, amount = struct.unpack('<BBH', r[:4])
    tr = Transaction()
    tr.source = nameList[sourceInd]
    tr.target = nameList[targetInd]
    tr.amount = amount
    return tr

def initiateRND(TX):
    global LONG_RND_STRING, bio
    LONG_RND_STRING = long_string(min(TX * (TR_SIZE-5), 1e6))
    bio = BytesIO(LONG_RND_STRING)

# Msg Type Note:
# 1':(0, 0, ('B', ('i', 0, set([{{Transaction from Alice to Gerald with 22}}]),
# '0E\x02 T\xf3\x05\xdc\xc6\xd8\x02\xa3\xb3D\xb4\xba\xe3\xd7<\xb1z\xb2\x9c/\x1a\xfdB\x9cZj\xe6\xbc\x9e\x16\x85\x05\x02!\x00\xd5\xee\xa2\xf1\xe7-\xbe\xb9\xefE\x8d\x12\xc4*\xe4D\x96\xa7\xa5\xbe\x13\xaa\x87\x93\x94c\xc4et\xa5\x1a\xc4')))
# 1:(3, 1, ('B', ('i', 1, set([{{Transaction from Francis to Eco with 86}}]))))
# 2:(1, 0, ('B', ('e', 0, (2, set([{{Transaction from Bob to Jessica with 65}}])))))
# 3:(0, 3, ('A', (1, ('B', (1, 1)))))
# 4:(0, 3, ('A', (2, ('A', (1, 1)))))
# 5:(3, 0, ('A', (0, ('C', (1, mpz(340L))))))
# 6:(3, 0, ('B', ('r', 0, 'asdasd')))

def deepDecode(m, msgTypeCounter):
    buf = BytesIO(m)
    mc, f, t, msgtype = struct.unpack('<IBBB', buf.read(7))
    trSet = set()
    msgTypeCounter[msgtype][0] += 1
    msgTypeCounter[msgtype][1] += len(m)
    if msgtype == 1:
        lenS, nrBr = struct.unpack('<IB', buf.read(5))
        trSet = buf.read(lenS)
        rh = buf.read(SHA_LENGTH)
        mb = []
        for nr in range(nrBr):
            mb.append(buf.read(SHA_LENGTH))
        sig = buf.read()
        return mc, (f, t, ('B', ('i', (trSet, rh, mb), sig)),)
    elif msgtype == 2:
        p2, trSetLen, nrBr = struct.unpack('<BIB', buf.read(6))
        trSet = buf.read(trSetLen)
        rh = buf.read(SHA_LENGTH)
        mb = []
        for nr in range(nrBr):
            mb.append(buf.read(SHA_LENGTH))
        sig = buf.read()
        return mc, (f, t, ('B', ('e', (p2, trSet, rh, mb), sig)),)
    elif msgtype == 3:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('B', (p2, p3)))),)
    elif msgtype == 4:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('A', (p2, p3)))),)
    elif msgtype == 5:
        p1, r = struct.unpack('<BH', buf.read(3))
        sig = boldyreva.deserialize1(buf.read())
        return mc, (f, t, ('A', (p1, ('C', (r, sig)))))
    elif msgtype == 6:
        p1, = struct.unpack('B', buf.read(1))
        hm = buf.read()
        return mc, (f, t, ('B', ('r', p1, hm)))
    elif msgtype == 7:
        id = struct.unpack('B', buf.read(1))[0]
        share = deserialize1(buf.read(PAIRING_SERIALIZED_1))
        return mc, (f, t, ('O', id, share))
    else:
        raise deepDecodeException()

def initiateThresholdSig(contents):
    global PK, SKs
    # print contents
    (l, k, sVK, sVKs, SKs) = pickle.loads(contents)
    PK, SKs = boldyreva.TBLSPublicKey(l, k, boldyreva.deserialize2(sVK), [boldyreva.deserialize2(sVKp) for sVKp in sVKs]), \
           [boldyreva.TBLSPrivateKey(l, k, boldyreva.deserialize2(sVK), [boldyreva.deserialize2(sVKp) for sVKp in sVKs], \
                           boldyreva.deserialize0(SKp[1]), SKp[0]) for SKp in SKs]

def initiateThresholdEnc(contents):
    global encPK, encSKs
    (l, k, sVK, sVKs, SKs) = pickle.loads(contents)
    encPK, encSKs = TPKEPublicKey(l, k, deserialize1(sVK), [deserialize1(sVKp) for sVKp in sVKs]), \
           [TPKEPrivateKey(l, k, deserialize1(sVK), [deserialize1(sVKp) for sVKp in sVKs], \
                           deserialize0(SKp[1]), SKp[0]) for SKp in SKs]

def initiateECDSAKeys(contents):
    global ecdsa_key_list
    ecdsa_key_list = []
    ecdsa_sec_list = pickle.loads(contents)
    for secret in ecdsa_sec_list:
        k = KEY()
        k.generate(secret)
        k.set_compressed(True)
        ecdsa_key_list.append(k)

def getEncKeys():
    return encPK, encSKs

def getKeys():
    return PK, SKs

def getECDSAKeys():
    return ecdsa_key_list

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def mylog(*args, **kargs):
    if not 'verboseLevel' in kargs:
        kargs['verboseLevel'] = 0
    if kargs['verboseLevel'] <= verbose:
        print " ".join([isinstance(arg, str) and arg or repr(arg) for arg in args])
        sys.stdout.flush()
        sys.stderr.flush()


def joinQueues(a, b):
    # Return an element from either a or b
    q = Queue(1)

    def _handle(chan):
        chan.peek()
        q.put(chan)

    Greenlet(_handle, a).start()
    Greenlet(_handle, b).start()
    c = q.get()
    if c is a: return 'a', a.get()
    if c is b: return 'b', b.get()


def makeBroadcastWithTag(tag, broadcast):
    def _bc(m):
        broadcast(
            (tag, m)
        )
    return _bc


def makeBroadcastWithTagAndRound(tag, broadcast, round):
    def _bc(m):
        broadcast(
            (tag, (round, m))
        )
    return _bc

def getSignatureCost():
    return signatureCost

def dummyCoin(round, N):
    return int(hashlib.md5(str(round)).hexdigest(), 16) % 2


class MonitoredInt(object):
    _getcallback = lambda _: None
    _setcallback = lambda _: None

    def _getdata(self):
        self._getcallback()
        return self.__data

    def _setdata(self, value):
        self.__data = value
        self._setcallback(value)

    def __init__(self, getCallback=lambda _: None, setCallback=lambda _: None):
        self._getcallback = lambda _: None
        self._setcallback = lambda _: None
        self._data = 0

    def registerGetCallBack(self, getCallBack):
        self._getcallback = getCallBack

    def registerSetCallBack(self, setCallBack):
        self._setcallback = setCallBack

    data = property(_getdata, _setdata)


def garbageCleaner(channel):  # Keep cleaning the channel
    while True:
        channel.get()


def loopWrapper(func):
    def _loop(*args, **kargs):
        while True:
            func(*args, **kargs)
    return _loop


class ACSException(Exception):
    pass

def greenletPacker(greenlet, name, parent_arguments):
    greenlet.name = name
    greenlet.parent_args = parent_arguments
    return greenlet

def greenletFunction(func):
    func.at_exit = lambda: None  # manual at_exit since Greenlet does not provide this event by default
    return func

def checkExceptionPerGreenlet(outfileName=None, ignoreHealthyOnes=True):
    mylog("Trying to detect greenlets...", verboseLevel=-2)
    if not outfileName:
        for ob in gc.get_objects():
            if not hasattr(ob, 'parent_args'):
                continue
            if not ob:
                continue
            if ignoreHealthyOnes and (not ob.exception):
                 continue
            mylog('%s[%s] called with parent arg\n(%s)\n%s' % (ob.name, repr(ob.args), repr(ob.parent_args),
                ''.join(traceback.format_stack(ob.gr_frame))), verboseLevel=-2)
            mylog(ob.exception, verboseLevel=-2)
    else:
        handler = open(outfileName, 'w')
        for ob in gc.get_objects():
            if not hasattr(ob, 'parent_args'):
                continue
            if not ob:
                continue
            if ignoreHealthyOnes and (not ob.exception):
                 continue
            handler.write('%s[%s] called with parent arg\n(%s)\n%s' % (ob.name, repr(ob.args), repr(ob.parent_args),
                ''.join(traceback.format_stack(ob.gr_frame))))
            handler.write(ob.exception)

if __name__ == '__main__':
    a = MonitoredInt()
    a.data = 1

    def callback(val):
        print "Callback called with", val

    a.registerSetCallBack(callback)
    a.data = 2
