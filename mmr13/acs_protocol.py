__author__ = 'aluex'

from gevent import Greenlet
from gevent.queue import Queue
from mmr13 import binary_consensus
from bkr_acs import acs
from utils import bcolors, mylog, MonitoredInt, callBackWrap

class Transaction:
    def __init__(self):
        self.from = 'Unknown'
        self.to = 'Unknown'
        self.amount = 0
        #### TODO: Define a detailed transaction

def consensusBroadcast(pid, N, t, msg, broadcast, receive):
    pass

def union(listOfTXSet):
    result = set() # Informal Union: actually we don't know how it compares ...
    for s in listOfTXSet:
        result.union(s)
    return result

# tx is the transaction we are going to include
def includeTransaction(pid, N, t, TXSet, broadcast, receive):

    for tx in TXSet:
        assert(isinstance(tx, Transaction))

    CBChannel = Queue()
    ACSChannel = Queue()
    TXSet = [{} for _ in range(N)]

    def make_bc_br(i):
        def _bc_br(m):
            broadcast(i, ('BC', m))
        return _bc_br

    def make_acs_br(i):
        def _acs_br(m):
            broadcast(i, ('ACS', m))
        return _acs_br

    def _listener():
        while True:
            sender, (tag, m) = receive()
            if tag == 'BC':
                CBChannel.put(sender, m)
            elif tag=='ACS':
                ACSChannel.put(
                    (sender, m)
                )

    def callbackFactoryBC():
        def _callback(packedNum): # now I know player j has succeeded in broadcasting
            j, txj = packedNum
            monitoredIntList[j].data = 1
            TXSet[j] = txj
        return _callback

    def callbackFactoryACS():
        def _callback(commonSet): # now I know player j has succeeded in broadcasting
            #######
            locker.put(commonSet)
        return _callback

    Greenlet(_listener).start()

    locker = Queue(1)
    includeTransaction.callbackCounter = 0
    monitoredIntList = [MonitoredInt() for _ in range(N)]

    Greenlet(callBackWrap(consensusBroadcast, callbackFactoryBC()), pid, N, t, TXSet, make_bc_br(pid), CBChannel.get).start()
    Greenlet(callBackWrap(acs, callbackFactoryACS()), pid, N, t, monitoredIntList, make_acs_br(pid), ACSChannel.get).start()
    commonSet = locker.get()

    return union([TXSet[x] for x in range(N) if commonSet[x]==1])



