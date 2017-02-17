# coding=utf-8
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
from utils import dummyCoin, greenletPacker, getKeys
from ..commoncoin.boldyreva_gipc import serialize, deserialize1, combine_and_verify


verbose = 0
from utils import makeCallOnce, \
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
            broadcast(v)

        relay = (makeCallOnce(lambda: _bc(0)),
                 makeCallOnce(lambda: _bc(1)))

        # Start by relaying my value
        relay[my_v]()
        outputed = []
        while True:
            (sender, v) = receive()

            assert v in (0, 1)
            assert sender in range(N)
            received[v].add(sender)
            # Relay after reaching first threshold
            if len(received[v]) >= t + 1:
                relay[v]()

            # Output after reaching second threshold
            if len(received[v]) >= 2 * t + 1:
                out[v]()
                if not v in outputed:
                    outputed.append(v)
                if len(outputed) == 2:
                    release()  # Release Channel
                    return  # We don't have to wait more

    return input

class CommonCoinFailureException(Exception):
    pass

def shared_coin(instance, pid, N, t, broadcast, receive):
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
    PK, SKs = getKeys()
    def _recv():
        while True:
            # New shares for some round r
            (i, (r, sig)) = receive()
            assert i in range(N)
            assert r >= 0
            received[r].add((i, serialize(sig)))

            # After reaching the threshold, compute the output and
            # make it available locally
            if len(received[r]) == t + 1:
                    h = PK.hash_message(str((r, instance)))
                    def tmpFunc(r, t):
                        # Verify and get the combined signature
                        s = combine_and_verify(h, dict(tuple((t, deserialize1(sig)) for t, sig in received[r])[:t+1]))
                        outputQueue[r].put(ord(s[0]) & 1)  # explicitly convert to int
                    Greenlet(
                        tmpFunc, r, t
                    ).start()

    greenletPacker(Greenlet(_recv), 'shared_coin_dummy', (pid, N, t, broadcast, receive)).start()

    def getCoin(round):
        broadcast((round, SKs[pid].sign(PK.hash_message(str((round,instance))))))  # I have to do mapping to 1..l
        return outputQueue[round].get()

    return getCoin


def arbitary_adversary(pid, N, t, vi, broadcast, receive):
    pass  # TODO: implement our arbitrary adversaries

globalState = defaultdict(str)  # Just for debugging

def initBeforeBinaryConsensus(): # A dummy function now
    '''
    Initialize all the variables used by binary consensus.
    Actually these variables should be described as local variables.
    :return: None
    '''
    pass


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

    makeBroadcastWithTag('V', broadcast)(vi)
    perplexed = mv84WaiterLock.get()  # See if I am perplexed

    makeBroadcastWithTag('B', broadcast)(perplexed)
    alert = mv84WaiterLock2.get() and 1 or 0  # See if we should alert


    decideChannel = Queue(1)
    greenletPacker(Greenlet(binary_consensus, pid, N, t, alert, decideChannel, broadcast, reliableBroadcastReceiveQueue.get),
        'mv84consensus.binary_consensus', (pid, N, t, vi, broadcast, receive)).start()
    agreedAlert = decideChannel.get()

    if agreedAlert:
        return 0  # some pre-defined default consensus value
    else:
        return vi


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


def binary_consensus(instance, pid, N, t, vi, decide, broadcast, receive):
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
    coinQ = Queue(1)
    bcQ = defaultdict(lambda: Queue(1))
    auxQ = defaultdict(lambda: Queue(1))

    def _recv():
        while True:  #not finished[pid]:
            (i, (tag, m)) = receive()
            if tag == 'B':
                # Broadcast message
                r, msg = m
                greenletPacker(Greenlet(bcQ[r].put, (i, msg)),
                    'binary_consensus.bcQ[%d].put' % r, (pid, N, t, vi, decide, broadcast, receive)).start() # In case they block the router
            elif tag == 'C':
                # A share of a coin
                greenletPacker(Greenlet(coinQ.put, (i, m)),
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

    coin = shared_coin(instance, pid, N, t, makeBroadcastWithTag('C', broadcast), coinQ.get)

    def getWithProcessing(r, binValues, callBackWaiter):
        def _recv(*args, **kargs):
            sender, v = auxQ[r].get(*args, **kargs)
            assert v in (0, 1)
            assert sender in range(N)
            received[v][r].add(sender)
            # Check if conditions are satisfied
            threshold = N - t  # 2*t + 1 # N - t
            if True: #not finished[pid]:
                if len(binValues) == 1:
                    if len(received[binValues[0]][r]) >= threshold and not callBackWaiter[r].full():
                        # Check passed
                        callBackWaiter[r].put(binValues)
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
    decidedNum = 0

    callBackWaiter = defaultdict(lambda: Queue(1))

    while True: # checkFinishedWithGlobalState(N): <- for distributed experiment we don't need this
        round += 1
        # Broadcast EST
        # TODO: let bv_broadcast receive
        bvOutputHolder = Queue(2)  # 2 possible values
        binValues = []

        def bvOutput(m):
            if not m in binValues:
                binValues.append(m)
                bvOutputHolder.put(m)

        def getRelease(channel):
            def _release():
                greenletPacker(Greenlet(garbageCleaner, channel),
                    'binary_consensus.garbageCleaner', (pid, N, t, vi, decide, broadcast, receive)).start()
            return _release

        br1 = greenletPacker(Greenlet(
            bv_broadcast(
                pid, N, t, makeBroadcastWithTagAndRound('B', broadcast, round),
                brcast_get(round), bvOutput, getRelease(bcQ[round])),
            est), 'binary_consensus.bv_broadcast(%d, %d, %d)' % (pid, N, t), (pid, N, t, vi, decide, broadcast, receive))
        br1.start()
        w = bvOutputHolder.get()  # Wait until output is not empty

        broadcast(('A', (round, w)))
        greenletPacker(Greenlet(loopWrapper(getWithProcessing(round, binValues, callBackWaiter))),
            'binary_consensus.loopWrapper(getWithProcessing(round, binValues, callBackWaiter))',
                    (pid, N, t, vi, decide, broadcast, receive)).start()

        values = callBackWaiter[round].get()  # wait until the conditions are satisfied
        s = coin(round)
        # Here corresponds to a proof that if one party decides at round r,
        # then in all the following rounds, everybody will propose r as an estimation. (Lemma 2, Lemma 1)
        # An abandoned party is a party who has decided but no enough peers to help him end the loop.
        # Lemma: # of abandoned party <= t
        if decided and decidedNum == s:  # infinite-message fix
            break
        if len(values) == 1:
            if values[0] == s:
                # decide s
                if not decided:
                    globalState[pid] = "%d" % s
                    decide.put(s)
                    decided = True
                    decidedNum = s

            else:
                pass
                # mylog('[%d] advances rounds from %d caused by values[0](%d)!=s(%d)' % (pid, round, values[0], s), verboseLevel=-1)
            est = values[0]
        else:
            # mylog('[%d] advances rounds from %d caused by len(values)>1 where values=%s' % (pid, round, repr(values)), verboseLevel=-1)
            est = s

    # mylog("[%d]b exits binary consensus" % pid)
