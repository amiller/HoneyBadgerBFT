__author__ = 'aluex'
from gevent import monkey
monkey.patch_all()

import sys
from gevent.queue import Queue
from gevent import Greenlet
import random
import hashlib
import gc
import traceback
import cPickle as pickle
from io import BytesIO
import struct
import gmpy2
from ecdsa_ssl import KEY


nameList = ["Alice", "Bob", "Christina", "David", "Eco", "Francis", "Gerald", "Harris", "Ive", "Jessica"]

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
ecdsa_key_list = []

from Crypto.Hash import SHA256
sha1hash = lambda x: SHA256.new(x).digest()

import sys
import os
sys.path.append(os.path.abspath('../commoncoin'))
import shoup


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

    #def getBitsRepr(self):
    #    return struct.pack('BBH', int(self.source.encode('hex'), 16) & 255, int(self.target.encode('hex'), 16) & 255,
    #                       self.amount)

def randomTransaction():
    tx = Transaction()
    tx.source = random.choice(nameList)
    tx.target = random.choice(nameList)
    tx.amount = random.randint(1, 100)
    return tx

def randomTransactionStr():
    return repr(randomTransaction())

class deepEncodeException(Exception):
    pass

class deepDecodeException(Exception):
    pass

class finishTransactionLeap(Exception):
    pass

# assumptions: amount of the money transferred can be expressed in 2 bytes.
def encodeTransaction(tr):
    sourceInd = nameList.index(tr.source)
    targetInd = nameList.index(tr.target)
    return struct.pack(
        '<BBH', sourceInd, targetInd, tr.amount
    )


# assumptions:
# + mc can be expressed in 4 bytes.
# + party index can be expressed in 1 byte.
# + round index can be expressed in 2 bytes.
# + transactions with ammount > 0 [THIS IS IMPORTANT for separation]
# + transaction set fragments is less than 2^32 bytes

def deepEncode(mc, m):
    buf = BytesIO()
    buf.write(struct.pack('<I', mc))
    f, t, (tag, c) = m
    buf.write(struct.pack('BB', f, t))
    # totally we have 4 msg types
    if c[0]=='i':
        buf.write('\x01')
        t2, p1, s, sig = c
        buf.write(struct.pack('B', p1))
        for tr in s:
            buf.write(encodeTransaction(tr))
        buf.write('\x00'*4)
        buf.write(sig)
    elif c[0]=='e':
        buf.write('\x02')
        t2, p1, (p2, s), sig = c
        buf.write(struct.pack('BB', p1, p2))
        buf.write(struct.pack('<I', len(s)))
        buf.write(s)  ## here we already have them encoded
        # for tr in s:
        #     buf.write(encodeTransaction(tr))
        # buf.write('\x00'*4)
        buf.write(sig)
    else:
        p1, (t2, m2) = c
        if t2 == 'B':
            buf.write('\x03')
        elif t2 == 'A':
            buf.write('\x04')
        elif t2 == 'C':
            buf.write('\x05')
            r, sig = m2
            buf.write(struct.pack('<BH', p1, r) + gmpy2.to_binary(sig)[2:])
            buf.seek(0)
            return buf.read()
        else:
            raise deepEncodeException()
        (p2, p3) = m2
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
# 1':(0, 0, ('B', ('i', 0, set([{{Transaction from Alice to Gerald with 22}}]),
# '0E\x02 T\xf3\x05\xdc\xc6\xd8\x02\xa3\xb3D\xb4\xba\xe3\xd7<\xb1z\xb2\x9c/\x1a\xfdB\x9cZj\xe6\xbc\x9e\x16\x85\x05\x02!\x00\xd5\xee\xa2\xf1\xe7-\xbe\xb9\xefE\x8d\x12\xc4*\xe4D\x96\xa7\xa5\xbe\x13\xaa\x87\x93\x94c\xc4et\xa5\x1a\xc4')))
# 1:(3, 1, ('B', ('i', 1, set([{{Transaction from Francis to Eco with 86}}]))))
# 2:(1, 0, ('B', ('e', 0, (2, set([{{Transaction from Bob to Jessica with 65}}])))))
# 3:(0, 3, ('A', (1, ('B', (1, 1)))))
# 4:(0, 3, ('A', (2, ('A', (1, 1)))))
# 5:(3, 0, ('A', (0, ('C', (1, mpz(340L))))))

def deepDecode(m, msgTypeCounter):
    buf = BytesIO(m)
    mc, f, t, msgtype = struct.unpack('<IBBB', buf.read(7))
    trSet = set()
    msgTypeCounter[msgtype] += len(m)
    if msgtype == 1:
        p1, = struct.unpack('B', buf.read(1))
        trRepr = buf.read(4)
        while trRepr != '\x00'*4:
            trSet.add(constructTransactionFromRepr(trRepr))
            trRepr = buf.read(4)
        sig = buf.read()
        return mc, (f, t, ('B', ('i', p1, trSet, sig)),)
    elif msgtype == 2:
        p1, p2 = struct.unpack('BB', buf.read(2))
        trSetLen = struct.unpack('<I', buf.read(4))
        trSet = buf.read(trSetLen)
        # trRepr = buf.read(4)
        # while trRepr != '\x00'*4:
        #    trSet.add(constructTransactionFromRepr(trRepr))
        #    trRepr = buf.read(4)
        sig = buf.read()
        return mc, (f, t, ('B', ('e', p1, (p2, trSet), sig)),)
    elif msgtype == 3:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('B', (p2, p3)))),)
    elif msgtype == 4:
        p1, p2, p3 = struct.unpack('BBB', buf.read(3))
        return mc, (f, t, ('A', (p1, ('A', (p2, p3)))),)
    elif msgtype == 5:
        p1, r = struct.unpack('<BH', buf.read(3))
        sig = gmpy2.from_binary('\x01\x01'+buf.read())
        return mc, (f, t, ('A', (p1, ('C', (r, sig)))))
    else:
        raise deepDecodeException()

def initiateThresholdSig(contents):
    global PK, SKs
    PK, SKs = pickle.loads(contents)
    #print PK
    #print SKs

def initiateECDSAKeys(contents):
    global ecdsa_key_list
    ecdsa_key_list = []
    ecdsa_sec_list = pickle.loads(contents)
    for secret in ecdsa_sec_list:
        k = KEY()
        k.generate(secret)
        k.set_compressed(True)
        ecdsa_key_list.append(k)

def setHash(s):
    result = 0
    for ele in s:
        result ^= hash(ele)
    return result

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


# Returns an idempotent function that only
def makeCallOnce(callback, *args, **kargs):
    called = [False]

    def callOnce():
        if called[0]: return
        called[0] = True
        callback(*args, **kargs)

    return callOnce


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
    # global signatureCost
    # signatureCost += 2048 / 8 * N
    return int(hashlib.md5(str(round)).hexdigest(), 16) % 2
    # return round % 2   # Somehow hashlib does not work well on EC2. I always get 0 from this function.


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

def checkExceptionPerGreenlet(ignoreHealthyOnes=True):
    mylog("Tring to detect greenlets...")
    for ob in gc.get_objects():
        if not hasattr(ob, 'parent_args'):
            continue
        if not ob:
            continue
        if ignoreHealthyOnes and (not ob.exception):
             continue
        mylog('%s[%s] called with parent arg\n(%s)\n%s' % (ob.name, repr(ob.args), repr(ob.parent_args),
            ''.join(traceback.format_stack(ob.gr_frame))), verboseLevel=-1)
        mylog(ob.exception)

if __name__ == '__main__':
    a = MonitoredInt()
    a.data = 1

    def callback(val):
        print "Callback called with", val

    a.registerSetCallBack(callback)
    a.data = 2
