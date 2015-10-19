# coding=utf-8
import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
from utils import dummyCoin, greenletPacker
# import random
import sys

verbose = 0
from utils import bcolors, mylog, joinQueues, makeCallOnce, \
    makeBroadcastWithTag, makeBroadcastWithTagAndRound, garbageCleaner, loopWrapper


# Input: a binary value
# Output: outputs one binary value, and thereafter possibly a second
# - If at least (t+1) of the honest parties input v, then v will be output by all honest parties
# (Note: it requires up to 2*t honest parties to deliver their messages. At the highest tolerance setting, this means *all* the honest parties)
# - If any honest party outputs a value, then it must have been input by some honest party. If only corrupted parties propose a value, it will never be output. 
def bv_broadcast(pid, N, t, broadcast, receive, output, release=lambda: None):
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
        # assert my_v in (0, 1)

        # We'll output each of (0,1) at most once
        out = (makeCallOnce(lambda: output(0)),
               makeCallOnce(lambda: output(1)))

        # We'll relay each of (0,1) at most once
        received = defaultdict(set)

        def _bc(v):
            # mylog('[%d]' % pid, 'Relaying', v)
            broadcast(v)

        relay = (makeCallOnce(lambda: _bc(0)),
                 makeCallOnce(lambda: _bc(1)))

        # Start by relaying my value
        relay[my_v]()
        outputed = []
        while True:
            mylog('[%d]bv Now executing receive at line 56' % pid)
            (sender, v) = receive()

            assert v in (0, 1)
            assert sender in range(N)
            received[v].add(sender)
            mylog('[%d]bv finished 56 with msg %s and received %s' % (pid, repr((sender, v)), repr(received)))
            # Relay after reaching first threshold
            if len(received[v]) >= t + 1:
                mylog('[%d]bv relayed on %d' % (pid, v))
                relay[v]()

            # Output after reaching second threshold
            if len(received[v]) >= 2 * t + 1:
                mylog('[%d]bv writing %d into output' % (pid, v))
                out[v]()
                if not v in outputed:
                    outputed.append(v)
                mylog('[%d]bv done with writing %d into output' % (pid, v))
                if len(outputed) == 2:
                    release()  # Release Channel
                    return  # We don't have to wait more

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
            # mylog('[%d] Now executing receive at line 114' % pid)
            (i, r) = receive()
            # mylog('[%d] finished line 114' % pid)
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

    greenletPacker(Greenlet(_recv), 'shared_coin_dummy', (pid, N, t, broadcast, receive)).start()

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

# finished = defaultdict(lambda: False)  # For the short cut
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
    This will achieve a consensus among all the inputs provided by honest parties,
    or raise an alert if failed to achieve one.
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

    def _listener():  # Hard-working Router for this layer
        while True:
            sender, (tag, m) = receive()
            # mylog("[%d] received %s" % (pid, repr(
            #     (sender, (tag, m))
            # )))
            if tag == 'V':
                mv84v[sender] = m
                if m != vi:
                    mv84ReceiveDiff.add(sender)
                    if len(mv84ReceiveDiff) >= (N - t) / 2.0:
                        mv84WaiterLock.put(True)
                # Fast-Stop: We don't need to wait for the rest (possibly)
                # malicious parties.
                if len(mv84v.keys()) >= N - t:
                    mv84WaiterLock.put(False)
            elif tag == 'B':
                mv84p[sender] = m
                if m:
                    mv84GetPerplex.add(sender)
                    if len(mv84GetPerplex) >= N - 2 * t:
                        mv84WaiterLock2.put(True)
                # Fast-Stop: We don't need to wait for the rest (possibly)
                # malicious parties.
                if len(mv84p.keys()) >= N - t:
                    mv84WaiterLock2.put(False)
            else:  # Re-route the msg to inner layer
                reliableBroadcastReceiveQueue.put(
                    (sender, (tag, m))
                )

    greenletPacker(Greenlet(_listener), 'mv84consensus._listener', (pid, N, t, vi, broadcast, receive)).start()

    mylog(bcolors.FAIL + "[%d] Starting Phase 1" % pid)
    makeBroadcastWithTag('V', broadcast)(vi)
    perplexed = mv84WaiterLock.get()  # See if I am perplexed

    mylog(bcolors.FAIL + "[%d] Starting Phase 2" % pid)
    makeBroadcastWithTag('B', broadcast)(perplexed)
    alert = mv84WaiterLock2.get() and 1 or 0  # See if we should alert

    mylog(bcolors.FAIL + "[%d] Starting binary consensus on alert: %d" % (pid, alert))

    decideChannel = Queue(1)
    greenletPacker(Greenlet(binary_consensus, pid, N, t, alert, decideChannel, broadcast, reliableBroadcastReceiveQueue.get),
        'mv84consensus.binary_consensus', (pid, N, t, vi, broadcast, receive)).start()
    agreedAlert = decideChannel.get()

    if agreedAlert:
        mylog(bcolors.FAIL + "[%d] agreed on Alert = True" % pid)
        return 0  # some pre-defined default consensus value
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

def checkFinishedWithGlobalState(N):
    '''
    Check if binary consensus is finished
    :param N: the number of parties
    :return: True if not finished, False if finished
    '''
    if len(globalState.keys()) < N:
        return True
    for i in globalState:
        if not globalState[i]:
            return True
    return False


def binary_consensus(pid, N, t, vi, decide, broadcast, receive):
    '''
    Binary consensus from [MMR 13]. It takes an input vi and will finally write the decided value into _decide_ channel.
    :param pid: my id number
    :param N: the number of parties
    :param t: the number of byzantine parties
    :param vi: input value, an integer
    :param decide: deciding channel
    :param broadcast: broadcast channel
    :param receive: receive channel
    :return:
    '''
    # Messages received are routed to either a shared coin, the broadcast, or AUX
    # finished[pid] = False
    coinQ = Queue(1)
    bcQ = defaultdict(lambda: Queue(1))
    auxQ = defaultdict(lambda: Queue(1))

    def _recv():
        while True:  #not finished[pid]:
            # mylog('[%d] Now executing receive at line 151' % pid)
            (i, (tag, m)) = receive()
            # mylog('[%d] finished 151 with msg %s' % (pid, repr((tag, m))))
            if tag == 'B':
                # Broadcast message
                r, msg = m
                greenletPacker(Greenlet(bcQ[r].put, (i, msg)),
                    'binary_consensus.bcQ[%d].put' % r, (pid, N, t, vi, decide, broadcast, receive)).start() # In case they block the router
            elif tag == 'C':
                # A share of a coin
                greenletPacker(Greenlet(coinQ.put, m),
                    'binary_consensus.coinQ.put', (pid, N, t, vi, decide, broadcast, receive)).start()
            elif tag == 'A':
                # Aux message
                r, msg = m
                greenletPacker(Greenlet(auxQ[r].put, (i, msg)),
                      'binary_consensus.auxQ[%d].put' % r, (pid, N, t, vi, decide, broadcast, receive)).start()
                pass

    greenletPacker(Greenlet(_recv), 'binary_consensus._recv', (pid, N, t, vi, decide, broadcast, receive)).start()

    def brcast_get(r):
        def _recv(*args, **kargs):
            return bcQ[r].get(*args, **kargs)

        return _recv

    received = [defaultdict(set), defaultdict(set)]

    def getWithProcessing(r, binValues, callBackWaiter):
        def _recv(*args, **kargs):
            mylog('[%d] Listening AUX' % pid)
            sender, v = auxQ[r].get(*args, **kargs)
            assert v in (0, 1)
            assert sender in range(N)
            received[v][r].add(sender)
            # Check if conditions are satisfied
            # mylog("[%d] beginChecking..." % pid)
            mylog("[%d] binValues %s" % (pid, repr(binValues)))
            mylog("[%d] received AUX. 0: %s, 1: %s" % (pid, repr(received[0][r]), repr(received[1][r])))
            threshold = N - t  # 2*t + 1 # N - t
            if True: #not finished[pid]:
                if len(binValues) == 1:
                    # print len(received[(binValues[0], r)])
                    if len(received[binValues[0]][r]) >= threshold and not callBackWaiter[r].full():
                        # Check passed
                        # mylog("[%d] Writing callBackWaiter" % pid)
                        callBackWaiter[r].put(binValues)
                        # mylog("[%d] Done with writing callBackWaiter" % pid)
                elif len(binValues) == 2:
                    if len(received[0][r].union(received[1][r])) >= threshold and not callBackWaiter[r].full():
                        callBackWaiter[r].put(binValues)
                    elif len(received[0][r]) >= threshold and not callBackWaiter[r].full():
                        callBackWaiter[r].put([0])
                    elif len(received[1][r]) >= threshold and not callBackWaiter[r].full():
                        callBackWaiter[r].put([1])
            return sender, v

        return _recv

    round = 0
    est = vi
    decided = False

    callBackWaiter = defaultdict(lambda: Queue(1))

    while checkFinishedWithGlobalState(N):
        round += 1
        mylog(bcolors.WARNING + '[%d]m enters round %d with decision %s' % (pid, round, globalState[pid] or 'None') + bcolors.ENDC, verboseLevel=-1)
        # Broadcast EST
        # TODO: let bv_broadcast receive
        bvOutputHolder = Queue(2)  # 2 possible values
        # bvAuxHolder = Queue(2) # turns out we don't need the output of aux
        binValues = []

        def bvOutput(m):
            if not m in binValues:
                binValues.append(m)
                # mylog("[%d]" % pid + ' has bin_values: ' + repr(binValues))
                # mylog(bcolors.OKGREEN + "[%d] Output holder received new value" % pid + bcolors.ENDC)
                bvOutputHolder.put(m)
                # mylog(bcolors.OKGREEN + "Done putting" + bcolors.ENDC)

        def getRelease(channel):
            def _release():
                #channel.maxsize = None
                greenletPacker(Greenlet(garbageCleaner, channel),
                    'binary_consensus.garbageCleaner', (pid, N, t, vi, decide, broadcast, receive)).start()
            return _release

        mylog('[%d]b begin phase 1 broadcasting' % pid)
        br1 = greenletPacker(Greenlet(
            bv_broadcast(
                pid, N, t, makeBroadcastWithTagAndRound('B', broadcast, round),
                brcast_get(round), bvOutput, getRelease(bcQ[round])),
            est), 'binary_consensus.bv_broadcast(%d, %d, %d)' % (pid, N, t), (pid, N, t, vi, decide, broadcast, receive))
        br1.start()
        mylog('[%d]b is waiting for phase 1' % pid)
        w = bvOutputHolder.get()  # Wait until output is not empty
        # br1.kill(block=False)
        mylog(bcolors.OKBLUE + '[%d]b Phase 1 done and starts phase 2 broadcasting' % pid + bcolors.ENDC)

        broadcast(('A', (round, w)))
        greenletPacker(Greenlet(loopWrapper(getWithProcessing(round, binValues, callBackWaiter))),
            'binary_consensus.loopWrapper(getWithProcessing(round, binValues, callBackWaiter))',
                    (pid, N, t, vi, decide, broadcast, receive)).start()

        comment = '''br2 = greenletPacker(Greenlet(
            bv_broadcast(
                pid, N, t, makeBroadcastWithTagAndRound('AUX', broadcast, round),
                getWithProcessing(round, binValues, callBackWaiter), lambda _: None, getRelease(auxQ[round])
            ), w), 'binary_consensus.bv_broadcast(%d, %d, %d)' % (pid, N, t), (pid, N, t, vi, decide, broadcast, receive))
        br2.start() #'''

        values = callBackWaiter[round].get()  # wait until the conditions are satisfied
        # br2.kill(block=False)
        mylog(bcolors.OKBLUE + '[%d]b Phase 2 done' % pid + bcolors.ENDC)
        #s = hash(round) % 2  ## TODO: Change this to dummy coin
        s = dummyCoin(round) % 2  ## TODO: Change this to dummy coin
        if len(values) == 1:
            if values[0] == s:
                # decide s
                if not decided:
                    mylog(bcolors.WARNING + "[%d]b decides on %d" % (pid, s) + bcolors.ENDC)
                    globalState[pid] = "decides on %d" % s
                    decide.put(s)
                    decided = True
                    # raw_input()
                # finished[pid] = True
                # return s
            est = values[0]
        else:
            est = s

    mylog("[%d]b exits binary consensus" % pid)
