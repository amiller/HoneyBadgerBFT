import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
import random
import sys
verbose = 0

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
def makeCallOnce(callback, *args):
    called = [False]

    def callOnce():
        if called[0]: return
        called[0] = True
        callback(*args)

    return callOnce


# The BV_Broadcast algorithm [MMR13]
# Input: a binary value
# Output: outputs one binary value, and thereafter possibly a second
# - If at least (t+1) of the honest parties input v, then v will be output by all honest parties
# (Note: it requires up to 2*t honest parties to deliver their messages. At the highest tolerance setting, this means *all* the honest parties)
# - If any honest party outputs a value, then it must have been input by some honest party. If only corrupted parties propose a value, it will never be output. 
def bv_broadcast(pid, N, t, broadcast, receive, output):
    assert N > 3 * t

    def input(my_v):
        # My initial input value is v in (0,1)
        assert my_v in (0, 1)

        # We'll output each of (0,1) at most once
        out = (makeCallOnce(lambda: output(0)),
               makeCallOnce(lambda: output(1)))

        # We'll relay each of (0,1) at most once
        received = defaultdict(set)

        def _bc(v):
            print '[%d]' % pid, 'Relaying', v
            broadcast(v)

        relay = (makeCallOnce(lambda: _bc(0)),
                 makeCallOnce(lambda: _bc(1)))

        # Start by relaying my value
        relay[my_v]()

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
                mylog('[%d] writing %d into output' % (pid, v))
                out[v]()

    return input


# A dummy version of the Shared Coin
def shared_coin_dummy(pid, N, t, broadcast, receive):
    received = defaultdict(set)
    outputQueue = defaultdict(lambda: Queue(1))

    def _recv():
        while True:
            # New shares for some round r
            (i, r) = receive()
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

def binary_consensus(pid, N, t, vi, broadcast, receive):
    # Messages received are routed to either a shared coin, the broadcast, or AUX
    coinQ = Queue(1)
    bcQ = defaultdict(lambda: Queue(1))
    auxQ = defaultdict(lambda: Queue(1))

    def _recv():
        while True:
            (i, (tag, m)) = receive()
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

    def make_bvbc_bc(r):
        def _bc(m):
            broadcast(('BC', (r, m)))

        return _bc

    def make_bvbc_aux(r):
        def _aux(m):
            broadcast(('AUX', (r, m)))

        return _aux

    def brcast_get(r):
        def _recv(*args, **kargs):
            return bcQ[r].get(*args, **kargs)
        return _recv

    received = defaultdict(set)

    def getWithProcessing(r, binValues):
        def _recv(*args, **kargs):
            sender, v = auxQ[r].get(*args, **kargs)
            assert v in (0, 1)
            assert sender in range(N)
            received[(v, r)].add(sender)
            # Check if conditions are satisfied
            if len(binValues) == 1:
                if len(received[(binValues[0], r)]) >= N-t:
                    # Check passed
                    callBackWaiter.put(binValues)
            else:
                if len(received[(0, r)].union(received[(1,r)])) >= N-t:
                    # Check passed
                    callBackWaiter.put(set(binValues))
                elif len(received[(0, r)]) >= N - t:
                    # Check passed
                    callBackWaiter.put([0])
                elif len(received[(1, r)]) >= N - t:
                    # Check passed
                    callBackWaiter.put([1])
            return sender, v
        return _recv

    Greenlet(_recv).start()

    round = 0
    est = vi

    while True:
        round += 1
        mylog('[%d] enters round %d' % (pid, round))
        # Broadcast EST
        # TODO: let bv_broadcast receive
        bvOutputHolder = Queue(2)  # 2 possile values
        # bvAuxHolder = Queue(2) # turns out we dont need the output of aux
        binValues = []
        callBackWaiter = Queue(1)

        def bvOutput(m):
            if not m in binValues:
                binValues.append(m)
                mylog("[%d]" % pid + 'has bin_values: ' + repr(binValues))
                mylog(bcolors.OKGREEN + "[%d] Output holder received new value" % pid + bcolors.ENDC)
                bvOutputHolder.put(m)
                mylog(bcolors.OKGREEN + "Done putting" + bcolors.ENDC)

        Greenlet(bv_broadcast(pid, N, t, make_bvbc_bc(round), brcast_get(round), bvOutput),est).start()
        w = bvOutputHolder.get()  # Wait until output is not empty
        mylog(bcolors.OKBLUE + '[%d] Phase 1 done' % pid + bcolors.ENDC)
        Greenlet(bv_broadcast(pid, N, t, make_bvbc_aux(round), getWithProcessing(round, binValues), lambda _: None),w).start()
        values = callBackWaiter.get() # wait until the conditions are satisfied
        mylog(bcolors.OKBLUE + '[%d] Phase 2 done' % pid + bcolors.ENDC)
        s = hash(round) % 2 ## TODO: Change this to dummy coin
        if len(values) == 1:
            if values[0] == s:
                # decide s
                mylog(bcolors.WARNING + "[%d] decides on %d" % (pid, s) + bcolors.ENDC)
                return s
        est = s

