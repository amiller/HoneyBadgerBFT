# coding=utf-8
import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
#import random
import sys
verbose = 0
from utils import bcolors, mylog, joinQueues, makeCallOnce, makeBroadcastWithTag

# Input: a binary value
# Output: outputs one binary value, and thereafter possibly a second
# - If at least (t+1) of the honest parties input v, then v will be output by all honest parties
# (Note: it requires up to 2*t honest parties to deliver their messages. At the highest tolerance setting, this means *all* the honest parties)
# - If any honest party outputs a value, then it must have been input by some honest party. If only corrupted parties propose a value, it will never be output. 
def bv_broadcast(pid, N, t, broadcast, receive, output):
    '''
    The BV_Broadcast algorithm [MMR13]
    :param pid: my id number
    :param N: the number of parties
    :param t: the number of byzantine parties
    :param broadcast: broadcast channel
    :param receive: receive channel
    :param output: output channel
    :return: None
    '''
    assert N > 3 * t

    def input(my_v):
        # my_v : input value

        # My initial input value is v in (0,1)
        #assert my_v in (0, 1)

        # We'll output each of (0,1) at most once
        out = (makeCallOnce(lambda: output(0)),
               makeCallOnce(lambda: output(1)))

        # We'll relay each of (0,1) at most once
        received = defaultdict(set)

        def _bc(v):
            mylog('[%d]' % pid, 'Relaying', v)
            broadcast(v)

        relay = (makeCallOnce(lambda: _bc(0)),
                 makeCallOnce(lambda: _bc(1)))

        # Start by relaying my value
        relay[my_v]()
        outputed = []
        while True:
            mylog('[%d] Now executing receive at line 86' % pid)
            (sender, v) = receive()
            mylog('[%d] finished 86' % pid)
            assert v in (0, 1)
            assert sender in range(N)
            received[v].add(sender)

            # Relay after reaching first threshold
            if len(received[v]) >= t + 1:
                relay[v]()

            # Output after reaching second threshold
            if len(received[v]) >= 2 * t + 1:
                mylog('[%d] writing %d into output' % (pid, v))
                out[v]()
                if not v in outputed:
                    outputed.append(v)
                mylog('[%d] done with writing %d into output' % (pid, v))
                if len(outputed) == 2:
                    return # We don't have to wait more

    return input


def shared_coin_dummy(pid, N, t, broadcast, receive):
    '''
    A dummy version of the Shared Coin
    :param pid: my id number
    :param N: the number of parties
    :param t: the number of byzantine parties
    :param broadcast: broadcast channel
    :param receive: receive channel
    :return: yield values b
    '''
    received = defaultdict(set)
    outputQueue = defaultdict(lambda: Queue(1))

    def _recv():
        while True:
            # New shares for some round r
            mylog('[%d] Now executing receive at line 114' % pid)
            (i, r) = receive()
            mylog('[%d] finished line 114' % pid)
            assert i in range(N)
            assert r >= 0
            if i in received[r]:
                continue
            received[r].add(i)

            # After reaching the threshold, compute the output and
            # make it available locally
            if len(received[r]) == N - t:
                b = hash(r) % 2
                outputQueue[r].put(b)

    Greenlet(_recv).start()

    # Broadcast our share
    round = 0
    while True:
        broadcast(round)
        # Wait until the value is ready
        b = outputQueue[round].get()
        # Advance round
        round += 1
        yield b


def arbitary_adversary(pid, N, t, vi, broadcast, receive):
    pass

# initDelivered = defaultdict(set)
# vectDelivered = defaultdict(set)
# vectDeliveredConsensus = defaultdict(set)
# initReceived = defaultdict(set)
# mvWaiterLock = defaultdict(lambda: Queue(1))
# mvWaiterLock2 = defaultdict(lambda: Queue(1))
# mvWaiterLock3 = defaultdict(lambda: Queue(1))
# V = defaultdict(lambda: defaultdict(lambda: 'bottom'))
# w = defaultdict(lambda:'bottom')
# W = defaultdict(lambda: defaultdict(lambda: 'bottom'))

finished = defaultdict(lambda: False)  # For the short cut
globalState = defaultdict(str)  # Just for debugging


def initBeforeBinaryConsensus():
    '''
    Initialize all the variables used by binary consensus.
    Actually these variables should be described as local variables.
    :return: None
    '''
    # This function is just for temporary use. It will be deprecated in the future.
    comment = '''
    global initDelivered, vectDelivered, vectDeliveredConsensus, mvWaiterLock, mvWaiterLock2, mvWaiterLock3, V, w, W, finished, globalState
    initDelivered = defaultdict(set)
    vectDelivered = defaultdict(set)
    vectDeliveredConsensus = defaultdict(set)
    #initReceived = defaultdict(set)
    mvWaiterLock = defaultdict(lambda: Queue(1))
    mvWaiterLock2 = defaultdict(lambda: Queue(1))
    mvWaiterLock3 = defaultdict(lambda: Queue(1))
    V = defaultdict(lambda: defaultdict(lambda: 'bottom'))
    w = defaultdict(lambda:'bottom')
    W = defaultdict(lambda: defaultdict(lambda: 'bottom'))
    finished = defaultdict(lambda: False)
    globalState = defaultdict(str)
    '''


def mv84consensus(pid, N, t, vi, broadcast, receive):
    '''
    Implementation of the multivalue consensus of [TURPIN, COAN, 1984]
    This will achieve a consensus among all the inputs provided by honest parties
    :param pid: my id number
    :param N: the number of parties
    :param t: the number of byzantine parties
    :param vi: input value, an integer
    :param broadcast: broadcast channel
    :param receive: receive channel
    :return: decided value or 0 (default value if failed to reach a concensus)
    '''
    # initialize v and p (same meaning as in the paper)
    mv84v = defaultdict(lambda: 'Empty')
    mv84p = defaultdict(lambda: False)
    # Initialize the locks and local variables
    mv84WaiterLock = Queue()
    mv84WaiterLock2 = Queue()
    mv84ReceiveDiff = set()
    mv84GetPerplex = set()
    reliableBroadcastReceiveQueue = Queue()

    def _listener():
        while True:
            sender, (tag, m) = receive()
            mylog("[%d] received %s" % (pid, repr((sender, (tag, m)))))
            if tag == 'VAL':
                mv84v[sender] = m
                if m != vi:
                    mv84ReceiveDiff.add(sender)
                    if len(mv84ReceiveDiff) > (N-t)/2:
                        mv84WaiterLock.put(True)
                if len(mv84v.keys()) >= N-t:
                    mv84WaiterLock.put(False)
            elif tag == 'BOOL':
                mv84p[sender] = m
                if m:
                    mv84GetPerplex.add(sender)
                    if len(mv84GetPerplex) >= N - 2*t:
                        mv84WaiterLock2.put(True)
                if len(mv84p.keys()) >= N-t:
                    mv84WaiterLock2.put(False)
            else:
                reliableBroadcastReceiveQueue.put(
                    (sender, (tag, m))
                )

    Greenlet(_listener).start()
    mylog(bcolors.FAIL + "[%d] Starting Phase 1" % pid)
    makeBroadcastWithTag('VAL', broadcast)(vi)
    perplexed = mv84WaiterLock.get()
    mylog(bcolors.FAIL + "[%d] Starting Phase 2" % pid)
    makeBroadcastWithTag('BOOL', broadcast)(perplexed)
    alert = mv84WaiterLock2.get() and 1 or 0
    mylog(bcolors.FAIL + "[%d] Starting binary consensus on alert: %d" % (pid, alert))
    agreedAlert = binary_consensus(pid, N, t, alert, broadcast, reliableBroadcastReceiveQueue.get)
    if agreedAlert:
        mylog(bcolors.FAIL + "[%d] agreed on Alert = True" % pid)
        return 0  # pre-defined default consensus value
    else:
        mylog(bcolors.FAIL + "[%d] agreed on %s" % (pid, repr(vi)))
        return vi


comment = '''
def MVBroadcast(pid, N, t, vi, cid, broadcast, receive):
    def make_mvbc_init():
        def _bc(m):
            broadcast(
                ('INIT', (m, cid, pid))
            )
        return _bc

    def make_mvbc_vect():
        def _bc(m, V):
            broadcast(
                ('VECT', (m, V, cid, pid))
            )
        return _bc
    reliableBroadcastReceiveQueue = Queue(1)
    threshold = N - t
    vCandidatesBeyondThreshold = []
    initDelivered[pid] = {}
    def T1():
        br1 = Greenlet(bv_broadcast(pid, N, t, make_mvbc_init(), reliableBroadcastReceiveQueue.get, lambda _: None), vi)
        br1.start()
        mvWaiterLock[pid].get() # wait for the conditions being satisfied
        br1.kill(block=False)
        vCandidates = defaultdict(lambda: 0)
        for tag, vj, cid, j in list(initDelivered[pid]):
            V[pid][j] = vj
            vCandidates[vj] += 1

        for key, values in vCandidates.items():
            if values >= threshold:
                vCandidatesBeyondThreshold.append(values)
        if len(vCandidatesBeyondThreshold) == 1:
            w[pid] = vCandidatesBeyondThreshold[0]

        br2 = Greenlet(bv_broadcast(pid, N, t, make_mvbc_vect(), reliableBroadcastReceiveQueue.get, lambda _: None), w[pid])
        br2.start()
        mvWaiterLock2[pid].get() # wait for the conditions being satisfied
        br2.kill(block=False)

        for tag, wj, Vj, cid, j in list(initDelivered[pid]):
            W[pid][j] = wj
        satisfied = True
        for j in range(N):
            for k in range(N):
                if not (W[pid][j] == W[pid][k] or W[pid][j]=='bottom' or W[pid][k] == 'bottom'):
                    satisfied = False
                    break
            if not satisfied:
                break
        bi = 0
        if satisfied:
            wCount = defaultdict(lambda: 0)
            for wi in W[pid]:
                wCount[wi] += 1
            for keys, values in wCount.items():
                if values>= threshold - t:
                    bi = 1
                    break
        ci = binary_consensus(pid, N, t, bi, broadcast, reliableBroadcastReceiveQueue.get)
        if ci == 0:
            return 'bottom'

        mvWaiterLock3.get()
        mylog("[%d] decides on multivalue %s" % (pid, vCandidatesBeyondThreshold[0]))
        return vCandidatesBeyondThreshold[0]


    def T2(): ######### Message Router
        while True:
            sender, (tag, m) = receive()
            if tag=='INIT':
                vj, cid, j = m
                initDelivered[pid].add((tag, vj, cid, j))
                if len(initDelivered[pid]) >= threshold:
                        mvWaiterLock[pid].put('ticket')
            elif tag=='VECT':
                wj, Vj, cid, j = m
                vectDelivered[pid].add((tag, wj, Vj, cid, j))
                if len(vectDelivered[pid]) >= threshold:
                        mvWaiterLock2[pid].put('ticket')
                if wj == vCandidatesBeyondThreshold[0]:
                    vectDeliveredConsensus[pid].add((tag, wj, Vj, cid, j))
                    if len(vectDelivered[pid]) >= threshold - t:
                        mvWaiterLock3[pid].put('ticket')
            else:
                reliableBroadcastReceiveQueue.put((pid, (tag, m)))

    Greenlet(T1).start()
    Greenlet(T2).start()
'''

def binary_consensus(pid, N, t, vi, broadcast, receive):
    # Messages received are routed to either a shared coin, the broadcast, or AUX
    coinQ = Queue(1)
    bcQ = defaultdict(lambda: Queue())
    auxQ = defaultdict(lambda: Queue())

    def _recv():
        while not finished[pid]:
            mylog('[%d] Now executing receive at line 151' % pid)
            (i, (tag, m)) = receive()
            mylog('[%d] finished 151 with msg %s' % (pid, repr((tag, m))))
            if tag == 'BC':
                # Broadcast message
                r, msg = m
                bcQ[r].put((i, msg))
            elif tag == 'COIN':
                # A share of a coin
                coinQ.put(m)
            elif tag == 'AUX':
                # Aux message
                r, msg = m
                auxQ[r].put((i, msg))
                pass


    Greenlet(_recv).start()

    def make_bvbc_bc(r):
        def _bc(m):
            broadcast(
                ('BC', (r, m))
            )

        return _bc

    def make_bvbc_aux(r):
        def _aux(m):
            broadcast(
                ('AUX', (r, m))
            )

        return _aux

    def brcast_get(r):
        def _recv(*args, **kargs):
            return bcQ[r].get(*args, **kargs)
        return _recv

    received = defaultdict(set)
    callBackWaiter = defaultdict(lambda: Queue(1))

    def getWithProcessing(r, binValues):
        def _recv(*args, **kargs):
            sender, v = auxQ[r].get(*args, **kargs)
            assert v in (0, 1)
            assert sender in range(N)
            received[(v, r)].add(sender)
            # Check if conditions are satisfied
            mylog("[%d] beginChecking..." % pid)
            mylog("[%d] binValues %s" % (pid, repr(binValues)))
            mylog("[%d] received. 0: %s, 1: %s" % (pid, repr(received[(0, r)]), repr(received[(1, r)])))
            threshold = N-t #2*t + 1 # N - t
            if not finished[pid]:
                if len(binValues) == 1:
                    print len(received[(binValues[0], r)])
                    if len(received[(binValues[0], r)]) >= threshold:
                        # Check passed
                        mylog("[%d] Writing callBackWaiter" % pid)
                        callBackWaiter[pid].put(binValues)
                        mylog("[%d] Done with writing callBackWaiter" % pid)
                else:
                    if len(received[(0, r)].union(received[(1, r)])) >= threshold:
                        # Check passed
                        callBackWaiter[pid].put(binValues)
                    elif len(received[(0, r)]) >= threshold:
                        # Check passed
                        callBackWaiter[pid].put([0])
                    elif len(received[(1, r)]) >= threshold:
                        # Check passed
                        callBackWaiter[pid].put([1])
            return sender, v
        return _recv

    round = 0
    est = vi

    while True:
        round += 1
        mylog(bcolors.WARNING + '[%d]m enters round %d' % (pid, round) + bcolors.ENDC)
        # Broadcast EST
        # TODO: let bv_broadcast receive
        bvOutputHolder = Queue(2)  # 2 possile values
        # bvAuxHolder = Queue(2) # turns out we dont need the output of aux
        binValues = []


        def bvOutput(m):
            if not m in binValues:
                binValues.append(m)
                mylog("[%d]" % pid + ' has bin_values: ' + repr(binValues))
                mylog(bcolors.OKGREEN + "[%d] Output holder received new value" % pid + bcolors.ENDC)
                bvOutputHolder.put(m)
                mylog(bcolors.OKGREEN + "Done putting" + bcolors.ENDC)

        mylog('[%d]m begin phase 1 broadcasting' % pid)
        br1 = Greenlet(bv_broadcast(pid, N, t, make_bvbc_bc(round), brcast_get(round), bvOutput),est)
        br1.start()
        mylog('[%d]m is waiting for phase 1' % pid)
        w = bvOutputHolder.get()  # Wait until output is not empty
        #br1.kill(block=False)
        mylog(bcolors.OKBLUE + '[%d]m Phase 1 done and starts phase 2 broadcasting' % pid + bcolors.ENDC)
        br2 = Greenlet(bv_broadcast(pid, N, t, make_bvbc_aux(round), getWithProcessing(round, binValues), lambda _: None), w)
        br2.start()
        #if len(binValues)

        values = callBackWaiter[pid].get() # wait until the conditions are satisfied
        #br2.kill(block=False)
        mylog(bcolors.OKBLUE + '[%d]m Phase 2 done' % pid + bcolors.ENDC)
        s = hash(round) % 2 ## TODO: Change this to dummy coin
        if len(values) == 1:
            if values[0] == s:
                # decide s
                mylog(bcolors.WARNING + "[%d]m decides on %d" % (pid, s) + bcolors.ENDC)
                globalState[pid] = "decides on %d" % s
                finished[pid] = True
                return s
        est = s


