__author__ = 'aluex'

from gevent import Greenlet
from gevent.queue import Queue
from mmr13 import binary_consensus
from bkr_acs import acs
from utils import bcolors, mylog, MonitoredInt, callBackWrap
from collections import defaultdict


class Transaction:
    def __init__(self):
        self.from='Unknown'
        self.to = 'Unknown'
        self.amount = 0
        #### TODO: Define a detailed transaction

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

def consensusBroadcast(pid, N, t, msg, broadcast, send, receive):
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
        phaseno = phaseno + 1


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



