from mmr13 import makeCallOnce, bv_broadcast, shared_coin_dummy, binary_consensus, bcolors, mylog, mv84consensus, initBeforeBinaryConsensus

#import random
from utils import myRandom as random
from gevent import Greenlet
import gevent
from gevent.queue import Queue
from utils import callBackWrap
# Run the BV_broadcast protocol with no corruptions and uniform random message delays
from utils import MonitoredInt, ACSException, greenletPacker
import time

lockBA = Queue(1)
defaultBA = []
lockBA.put(1)


def acs(pid, N, t, Q, broadcast, receive):
    assert(isinstance(Q, list))
    assert(len(Q) == N)
    decideChannel = [Queue(1) for _ in range(N)]
    receivedChannelsFlags = []

    def callbackFactory(i):
        def _callback(val): # Get notified for i
            # Greenlet(callBackWrap(binary_consensus, callbackFactory(i)), pid,
            #         N, t, 1, make_bc(i), reliableBroadcastReceiveQueue[i].get).start()
            receivedChannelsFlags.append(i)
            mylog('B[%d]binary consensus_%d_starts with 1 at %f' % (pid, i, time.time()), verboseLevel=-1)
            greenletPacker(Greenlet(binary_consensus, pid,
                N, t, 1, decideChannel[i], make_bc(i), reliableBroadcastReceiveQueue[i].get),
                    'acs.callbackFactory.binary_consensus', (pid, N, t, Q, broadcast, receive)).start()
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

    greenletPacker(Greenlet(_listener), 'acs._listener', (pid, N, t, Q, broadcast, receive)).start()

    BA = [0]*N
    locker = Queue(1)
    locker2 = Queue(1)
    callbackCounter = [0]

    comment = '''def callbackFactory(i):
        def _callback(result):
            BA[i] = result
            if result:
                if callbackCounter[0] >= 2*t:
                        locker.put("Key") # Now we've got 2t+1 1's
                callbackCounter[0] += 1
        return _callback'''

    def listenerFactory(i, channel):
        def _listener():
            BA[i] = channel.get()
            if BA[i]:
                mylog('B[%d]binary consensus_%d_ends at %f' % (pid, i, time.time()), verboseLevel=-1)
                if callbackCounter[0] >= 2*t and (not locker2.full()):
                        locker2.put("Key")  # Now we've got 2t+1 1's
                callbackCounter[0] += 1
                if callbackCounter[0] >= N-t and (not locker.full()):  # if we have all of them responded
                        locker.put("Key")
        return _listener

    for i in range(N):
        greenletPacker(Greenlet(listenerFactory(i, decideChannel[i])),
            'acs.listenerFactory(i, decideChannel[i])', (pid, N, t, Q, broadcast, receive)).start()

    locker2.get()
    # Now we feed 0 to all the other binary consensus protocols
    for i in range(N):
        if not i in receivedChannelsFlags:
            mylog('B[%d]binary_%d_starts with 0 at %f' % (pid, i, time.time()))
            greenletPacker(Greenlet(binary_consensus, pid, N, t, 0,
                     decideChannel[i], make_bc(i), reliableBroadcastReceiveQueue[i].get),
                           'acs.binary_consensus', (pid, N, t, Q, broadcast, receive)).start()
    locker.get()  # Now we can check'''
    BA = checkBA(BA, N, t)
    # gevent.sleep(1)
    mylog(bcolors.UNDERLINE + "[%d] Get subset %s" % (pid, BA) + bcolors.ENDC)
    return BA

comment = '''
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
    callbackCounter = [0]

    def callbackFactory(i):
        def _callback(result):
            BA[i] = result
            if result:
                if callbackCounter[0] >= 2*t:
                        locker.put("Key") # Now we've got 2t+1 1's
                callbackCounter[0] += 1
        return _callback


    for i in range(N):
        Greenlet(callBackWrap(binary_consensus, callbackFactory(i)), pid,
                     N, t, Q[i], make_bc(i), reliableBroadcastReceiveQueue[i].get).start()
    locker.get()
    mylog(bcolors.UNDERLINE + "[%d] Get subset %s" % (pid, BA) + bcolors.ENDC)
    return BA
    #open('result','a').write("[%d] Get subset %s" % (pid, BA))
'''

def checkBA(BA, N, t):
    global defaultBA
    if sum(BA) <= 2*t:  # If acs failed, we use a pre-set default common subset
        raise ACSException
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
               greenletPacker(Greenlet(_deliver, j),
                   'random_delay_acs._deliver', (N, t, inputs)).start_later(random.random()*maxdelay)

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
                greenletPacker(Greenlet(modifyMonitoredInt, input_clone[j]),
                    'random_delay_acs.modifyMonitoredInt', (N, t, inputs)).start_later(maxdelay * random.random())
            th = greenletPacker(Greenlet(acs, i, N, t, input_clone, bc, recv), 'random_delay_acs.acs', (N, t, inputs))
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

