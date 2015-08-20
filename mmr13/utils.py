__author__ = 'aluex'
import sys
from gevent.queue import Queue
from gevent import Greenlet

verbose = 0


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


if __name__ == '__main__':
    a = MonitoredInt()
    a.data = 1

    def callback(val):
        print "Callback called with", val

    a.registerSetCallBack(callback)
    a.data = 2
