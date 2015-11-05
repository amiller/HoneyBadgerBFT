__author__ = 'aluex'
import sys
import gevent.monkey
from gevent.queue import Queue
from gevent import Greenlet
import random
import hashlib
import gc
import traceback

gevent.monkey.patch_all()

verbose = -1
goodseed = random.randint(1, 10000)
myRandom = random.Random(goodseed)

signatureCost = 0

def callBackWrap(func, callback):
    def _callBackWrap(*args, **kargs):
        result = func(*args, **kargs)
        callback(result)

    return _callBackWrap


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
    global signatureCost
    signatureCost += 2048 / 8 * N
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

def checkExceptionPerGreenlet():
    mylog("Tring to detect greenlets...")
    for ob in gc.get_objects():
        if not hasattr(ob, 'parent_args'):
            continue
        if not ob:
            continue
        # if not ob.exception:
        #     continue
        mylog('%s[%s] called with parent arg\n(%s)\n%s' % (ob.name, repr(ob.args), repr(ob.parent_args),
                                                           ''.join(traceback.format_stack(ob.gr_frame))), verboseLevel=-1)

if __name__ == '__main__':
    a = MonitoredInt()
    a.data = 1

    def callback(val):
        print "Callback called with", val

    a.registerSetCallBack(callback)
    a.data = 2
