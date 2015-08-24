from mmr13 import makeCallOnce, bv_broadcast, shared_coin_dummy, binary_consensus, bcolors, mylog, mv84consensus, initBeforeBinaryConsensus

#import random
from utils import myRandom as random
from gevent import Greenlet
import gevent
from gevent.queue import Queue
from utils import callBackWrap
# Run the BV_broadcast protocol with no corruptions and uniform random message delays
from utils import MonitoredInt, ACSException

lockBA = Queue(1)
defaultBA = []
lockBA.put(1)


def checkBA(BA, N, t):
    global defaultBA
    if sum(BA) <= 2*t:  # If acs failed, we use a preset default common subset
        # raise ACSException
        # This part should never be executed
        if not defaultBA:
            lockBA.get()
            if not defaultBA:
                num = random.randint(2*t+1, N)
                defaultBA = [1]*num+[0]*(N-num)
                random.shuffle(defaultBA)
            lockBA.put(1)
        return [_ for _ in defaultBA]  # Clone
    return BA

def acs(pid, N, t, Q, broadcast, receive):
    assert(isinstance(Q, list))
    assert(len(Q) == N)

    def callbackFactory(i):
        def _callback(val): # Get notified for i
            Greenlet(callBackWrap(binary_consensus, callbackFactory(i)), pid,
                     N, t, 1, make_bc(i), reliableBroadcastReceiveQueue[i].get).start()
        return _callback

    for i, q in enumerate(Q):
        assert(isinstance(q, MonitoredInt))
        q.registerSetCallBack(callbackFactory(i))

    def make_bc(i):
        def _bc(m):
            broadcast(
                (i, m)
            )
        return _bc

    reliableBroadcastReceiveQueue = [Queue() for x in range(N)]

    def _listener():
        while True:
            sender, (instance, m) = receive()
            #mylog("[%d] received %s on instance %d" % (pid, repr((sender, m)), instance))
            reliableBroadcastReceiveQueue[instance].put(
                    (sender, m)
                )

    Greenlet(_listener).start()

    BA = [0]*N
    locker = Queue(1)
    acs.callbackCounter = 0

    def callbackFactory(i):
        def _callback(result):
            BA[i] = result
            if result:
                if acs.callbackCounter >= 2*t:
                        locker.put("Key") # Now we've got 2t+1 1's
                acs.callbackCounter += 1
        return _callback

    locker.get()
    BA = checkBA(BA, N, t)
    mylog(bcolors.UNDERLINE + "[%d] Get subset %s" % (pid, BA) + bcolors.ENDC)
    return BA

def acs_mapping(pid, N, t, Q, broadcast, receive):
    assert(isinstance(Q, list))
    assert(len(Q) == N)

    def make_bc(i):
        def _bc(m):
            broadcast(
                (i, m)
            )
        return _bc

    reliableBroadcastReceiveQueue = [Queue() for x in range(N)]

    def _listener():
        while True:
            sender, (instance, m) = receive()
            mylog("[%d] received %s on instance %d" % (pid, repr((sender, m)), instance))
            reliableBroadcastReceiveQueue[instance].put(
                    (sender, m)
                )

    Greenlet(_listener).start()

    BA = [0]*N
    locker = Queue(1)
    acs_mapping.callbackCounter = 0

    def callbackFactory(i):
        def _callback(result):
            BA[i] = result
            if result:
                if acs.callbackCounter >= 2*t:
                        locker.put("Key") # Now we've got 2t+1 1's
                acs_mapping.callbackCounter += 1
        return _callback


    for i in range(N):
        Greenlet(callBackWrap(binary_consensus, callbackFactory(i)), pid,
                     N, t, Q[i], make_bc(i), reliableBroadcastReceiveQueue[i].get).start()
    locker.get()
    mylog(bcolors.UNDERLINE + "[%d] Get subset %s" % (pid, BA) + bcolors.ENDC)
    return BA
    #open('result','a').write("[%d] Get subset %s" % (pid, BA))

def random_delay_acs(N, t, inputs):

    assert(isinstance(inputs, list))

    maxdelay = 0.01

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
           def _deliver(j):
               # print 'Delivering', v, 'from', i, 'to', j
               mylog(bcolors.OKGREEN + "MSG: [%d] -> [%d]: %s" % (i, j, repr(v)) + bcolors.ENDC)
               buffers[j].put((i,v))
               mylog(bcolors.OKGREEN + "     [%d] -> [%d]: Finish" % (i, j) + bcolors.ENDC)

           for j in range(N):
               Greenlet(_deliver, j).start_later(random.random()*maxdelay)

        return _broadcast

    def modifyMonitoredInt(monitoredInt):
        monitoredInt.data = 1

    while True:
        initBeforeBinaryConsensus()
        buffers = map(lambda _: Queue(1), range(N))
        ts = []
        #cid = 1
        for i in range(N):
            bc = makeBroadcast(i)
            recv = buffers[i].get #buffers[i].get
            #vi = random.randint(0, 10)
            input_clone = [MonitoredInt() for _ in range(N)]
            for j in range(N):
                Greenlet(modifyMonitoredInt, input_clone[j]).start_later(maxdelay * random.random())
            th = Greenlet(acs, i, N, t, input_clone, bc, recv)
            th.start() # start_later(random.random() * maxdelay)
            ts.append(th)

        #if True:
        try:
            gevent.joinall(ts)
            break
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "End"

if __name__=='__main__':
    #initTor()
    print "[ =========== ]"
    print "Testing binary consensus..."
    print "Testing ACS with different inputs..."
    Q = [1]*(2*1+1+1)+[0]*1
    random.shuffle(Q)
    random_delay_acs(5, 1, Q)

