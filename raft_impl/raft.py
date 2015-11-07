#!/Users/aluex/anaconda/bin/python
##################################
from gevent import monkey
monkey.patch_all()

import gevent
from gevent import Greenlet
from gevent.queue import Queue
# from collections import defaultdict
import random
# import json
import sys
import yaml
import time
from gevent import monkey
from gevent.lock import Semaphore

monkey.patch_all()

INF = 1e40
RPC_TIMEOUT = 0.05
ELECTION_TIMEOUT = 0.3000  # 0.1: repeat election, 0.5: unstable (leader may appear, but can be replaced), 1.0: stable leadership
# When DELAY_MAX = 0.4, DELAY_MIN = 0.02
CLIENT_DELAY = 3  # the maximum client delay
BATCH_SIZE = 1
RECV_TIMEOUT = 0.02
SEND_TIMEOUT = 0.02
RECV_CLIENT_TIMEOUT = 0.1

NETWORK_DELAY_MAX = 0.5  # seconds
NETWORK_DELAY_MIN = 0.3

TIME_START = 0

MSG_TOTAL = 5
ELECTION_TOTAL = 0
ELECTION_SUCCEED = 0

lock_total = Semaphore()
lock_succeed = Semaphore()
verbose = 0

sys.stderr = open('log', 'w') # re-direct stderr

def mylog(*args, **kargs):
    if not 'verboseLevel' in kargs:
        kargs['verboseLevel'] = 0
    if kargs['verboseLevel'] <= verbose:
        print " ".join([isinstance(arg, str) and arg or repr(arg) for arg in args])
        sys.stdout.flush()
        sys.stderr.flush()


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def raftServer(pid, N, t, broadcast, send, receive, recvClient, output, getTime, getElectionTimeDelay):
    def sendRequest(j, m):
        send(j, ('request', m))

    def sendResponse(j, m):
        send(j, ('response', m))

    def makeElectionTime():
        return getTime() + getElectionTimeDelay()

    def run(v):
        run.pid = pid
        # Here we just ignore the input
        run.state = 'follower'
        run.term = 1
        run.votedFor = None
        run.electionTimeout = makeElectionTime()
        run.voteGranted = [False] * N
        run.matchIndex = [0] * N
        run.nextIndex = [1] * N
        run.rpcDue = [0] * N
        run.log = []
        run.commitIndex = 0
        run.heartbeatDue = [0] * N

        def displayInfo(verboseLevel=0):
            if verbose >= verboseLevel:
                info = dict(
                    now=getTime(),
                    state=run.state,
                    term=run.term,
                    votedFor=run.votedFor,
                    electionTimeout=run.electionTimeout,
                    voteGranted=run.voteGranted,
                    matchIndex=run.matchIndex,
                    nextIndex=run.nextIndex,
                    rpcDue=run.rpcDue,
                    log=run.log,
                    commitIndex=run.commitIndex,
                    heartbeatDue=run.heartbeatDue
                )
                print yaml.dump(info)

        mylog("[%d] Initing..." % run.pid)
        displayInfo()
        # Setup the client-msg monitor
        mylog("[%d] Raft server started." % (run.pid))

        def onLeave():
            # Now we are done, in case that we didn't lose messages
            mylog(bcolors.BOLD + '[%d] Total election: %d, success election: %d' % (
                run.pid, ELECTION_TOTAL, ELECTION_SUCCEED) + bcolors.ENDC, verboseLevel=-1)
            sys.exit(0)

        def clientCallBack(msg):
            if msg == '#':
                onLeave()

            if run.state == 'leader':
                mylog(bcolors.WARNING + "\b[%d] received msg from client: %s" % (run.pid, repr(msg)) + bcolors.ENDC)
                run.log.append(dict(term=run.term, msg=msg))
                #Greenlet(clientMonitor).start_later(0)
                ############################## Send msg to the leader

        def clientMonitor():
            while True:
                try:
                    msg = recvClient(timeout=RECV_CLIENT_TIMEOUT)
                    clientCallBack(msg)
                except gevent.queue.Empty:
                    mylog("[%d] no client msg" % run.pid, verboseLevel=1)

        mylog("[%d] starts listening..." % (run.pid))
        Greenlet(clientMonitor).start()
        ##########################
        def accessLog(index):
            if index < 1 or index > len(run.log):
                return {'term': 0}
            return run.log[index - 1]

        def stepDown(newTerm):
            run.term = newTerm
            run.state = 'follower'
            run.votedFor = None
            if run.electionTimeout <= getTime() or run.electionTimeout == INF:
                run.electionTimeout = makeElectionTime()

        #############################
        def startNewElection():
            if (run.state == 'follower' or run.state == 'candidate') \
                    and run.electionTimeout <= getTime():
                mylog(bcolors.OKBLUE + "[%d] Starting a new election." % run.pid + bcolors.ENDC)
                global ELECTION_TOTAL
                lock_total.acquire()
                ELECTION_TOTAL += 1
                lock_total.release()
                run.electionTimeout = makeElectionTime()
                run.term += 1
                run.votedFor = run.pid
                run.state = 'candidate'
                run.voteGranted = [False] * N
                run.matchIndex = [0] * N
                run.nextIndex = [1] * N
                run.rpcDue = [0] * N
                run.heartbeatDue = [0] * N

        def sendRequestVote(j):
            if (run.state == 'candidate' and run.rpcDue[j] <= getTime()):
                run.rpcDue[j] = getTime() + RPC_TIMEOUT
                sendRequest(j, {
                    'from': run.pid,
                    'to': j,
                    'type': 'RequestVote',
                    'term': run.term,
                    'lastLogTerm': accessLog(len(run.log)),
                    'lastLogIndex': len(run.log)
                })

        def count(container, value):
            return len([1 for x in container if container[x] == value])

        def becomeLeader():
            if (run.state == 'candidate' and count(run.voteGranted, True) + 1 > N / 2):
                mylog("=" * 30)  # decorating
                mylog(bcolors.WARNING + "[%d] is now the leader." % run.pid + bcolors.ENDC)
                mylog("=" * 30)
                global ELECTION_SUCCEED
                lock_succeed.acquire()
                ELECTION_SUCCEED += 1
                lock_succeed.release()
                run.state = 'leader'
                run.nextIndex = [len(run.log) + 1] * N
                run.rpcDue = [INF] * N
                run.heartbeatDue = [0] * N
                run.electionTimeout = INF

        def sendAppendEntries(j):  # Act as heart beats also
            if (run.state == 'leader' and
                    (run.heartbeatDue[j] <= getTime() or
                         (run.nextIndex[j] <= len(run.log) and run.rpcDue[j] <= getTime()))):
                #displayInfo()
                prevIndex = run.nextIndex[j] - 1
                lastIndex = min(prevIndex + BATCH_SIZE, len(run.log))
                if (run.matchIndex[j] + 1 < run.nextIndex[j]):
                    lastIndex = prevIndex
                sendRequest(j, {
                    'from': run.pid,
                    'to': j,
                    'type': 'AppendEntries',
                    'term': run.term,
                    'prevIndex': prevIndex,
                    'prevTerm': accessLog(prevIndex) and accessLog(prevIndex)['term'] or 0,
                    'entries': run.log[prevIndex:lastIndex],  # To create a copy
                    'commitIndex': min(run.commitIndex, lastIndex)
                })
                run.rpcDue[j] = getTime() + RPC_TIMEOUT
                run.heartbeatDue[j] = getTime() + ELECTION_TIMEOUT / 2

        def advanceCommitIndex():
            mylog("[%d] advancing commitment: %s" % (run.pid, run.matchIndex), verboseLevel=1)
            mylog("[%d] has self committed to the first %d log items" % (run.pid, run.commitIndex), verboseLevel=1)
            mylog("[%d] log: %s" % (run.pid, repr(run.log)), verboseLevel=1)
            matchIndexArray = run.matchIndex[:]
            matchIndexArray[run.pid] = len(run.log)
            #mylog(matchIndexArray)
            n = sorted(matchIndexArray)[N / 2]
            if (run.state == 'leader' and (accessLog(n) == None or accessLog(n)['term'] == run.term)):
                run.commitIndex = max(run.commitIndex, n)
                if run.commitIndex == MSG_TOTAL - 1:
                    mylog(bcolors.BOLD + '[%d] All messages are committed, we are done!' % run.pid + bcolors.ENDC)
                    onLeave()

        def handleRequestVoteRequest(request):
            if run.term < request['term']:
                stepDown(request['term'])
            granted = False
            if (run.term == request['term'] and
                    (run.votedFor == None or run.votedFor == request['from']) and
                    (accessLog(len(run.log)) == None or run.log == [] or request['lastLogTerm'] > run.log[-1]['term'] or
                         (request['lastLogTerm'] == run.log[-1]['term'] and
                                  request['lastLogIndex'] >= len(run.log)))):
                granted = True
                run.votedFor = request['from']
                run.electionTimeout = makeElectionTime()
            sendResponse(request['from'], {
                'type': "RequestVote",
                'from': run.pid,
                'term': run.term,
                'granted': granted
            })

        def handleRequestVoteReply(reply):
            if (run.term < reply['term']):
                stepDown(reply['term'])
            if (run.state == 'candidate' and run.term == reply['term']):
                run.rpcDue[reply['from']] = INF
                run.voteGranted[reply['from']] = reply['granted']

        def handleAppendEntriesRequest(req):
            success = False
            matchIndex = 0
            if run.term < req['term']:
                stepDown(req['term'])
            if run.term == req['term']:
                run.state = 'follower'
                run.electionTimeout = makeElectionTime()
                if (req['prevIndex'] == 0 or
                        (req['prevIndex'] <= len(run.log) and
                             (accessLog(req['prevIndex']) == None or \
                                          accessLog(req['prevIndex'])['term'] == req['prevTerm']))):
                    success = True
                    index = req['prevIndex']
                    for i in range(len(req['entries'])):
                        index += 1
                        if accessLog(index) == None or accessLog(index)['term'] != req['entries'][i]['term']:
                            while len(run.log) > index - 1:
                                run.log.pop()
                            run.log.append(req['entries'][i])
                    matchIndex = index
                    run.commitIndex = max(run.commitIndex, req['commitIndex'])
            sendResponse(req['from'], {
                'type': "AppendEntries",
                'from': run.pid,
                'term': run.term,
                'success': success,
                'matchIndex': matchIndex})

        def handleAppendEntriesReply(rep):
            if run.term < rep['term']:
                stepDown(rep['term'])
            if run.state == 'leader' and run.term == rep['term']:
                if rep['success']:
                    run.matchIndex[rep['from']] = max(run.matchIndex[rep['from']], rep['matchIndex'])
                    run.nextIndex[rep['from']] = rep['matchIndex'] + 1
                else:
                    run.nextIndex[rep['from']] = max(1, run.nextIndex[rep['from']] - 1)
                run.rpcDue[rep['from']] = 0

        def handleMessage(packedMsg):
            if run.state == 'stopped':
                return
            direction, msg = packedMsg
            if msg['type'] == 'RequestVote':
                if direction == 'request':
                    handleRequestVoteRequest(msg)
                else:
                    handleRequestVoteReply(msg)
            elif msg['type'] == 'AppendEntries':
                if direction == 'request':
                    handleAppendEntriesRequest(msg)
                else:
                    handleAppendEntriesReply(msg)

        mylog("[%d] Counting down...\n\n" % run.pid)
        while True:
            startNewElection()
            becomeLeader()
            advanceCommitIndex()
            for i in range(N):
                if i != run.pid:
                    sendRequestVote(i)
                    sendAppendEntries(i)
            try:
                #mylog("[%d] tries to fetch a msg" % run.pid)
                result = receive(timeout=RECV_TIMEOUT)
                #mylog("[%d] got a msg: %s" % (run.pid, repr(result)))
                senderID, packedMSG = result
                handleMessage(packedMSG)
            except gevent.queue.Empty:
                pass  #Idle
        mylog("[%d] Reaches the end of the [run] function" % run.pid)

    return run


# clientsChannel = map(lambda _: Queue(1), inputs)
# timeOut is a function provides a timeout like Javascript
# Run the protocol with no corruptions, uniform random message delays
def runRaft(inputs, clientsChannel, t, tMin, tMax, getTime):  # Everyone broadcasts a msg in different delay

    N = len(inputs)
    buffers = map(lambda _: Queue(), inputs)
    # Instantiate the "broadcast" instruction for node i
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                buffers[j].put((i, v))

            for j in range(N):
                Greenlet(_deliver, j).start_later(tMin + random.random() * (tMax - tMin))

        return _broadcast

    def makeSend(i):
        def _send(j, v):
            mylog(bcolors.OKGREEN + "[m] %d -> %d\n\t\t%s" % (i, j, repr(v)) + bcolors.ENDC)
            while True:
                try:
                    buffers[j].put((i, v), timeout=SEND_TIMEOUT)
                    break
                except gevent.queue.Full:
                    pass

        def _async_send(j, v):
            #Greenlet(_send, j, v).start()
            Greenlet(_send, j, v).start_later(tMin + random.random() * (tMax - tMin))

        #return _send
        return _async_send

    def makeReceiveFromClient(i):
        return clientsChannel[i].get

    def makeOutput(i):
        def _output(v):
            mylog('[%d]' % i, 'output:', v)

        return _output

    def makeReceive(i):
        return buffers[i].get

    def getElectionTime():
        return (1 + random.random()) * ELECTION_TIMEOUT

    ts = []
    for i in range(N):
        bc = makeBroadcast(i)
        recv = makeReceive(i)
        client = makeReceiveFromClient(i)
        outp = makeOutput(i)
        snd = makeSend(i)
        inp = raftServer(i, N, t, bc, snd, recv, client, outp, getTime, getElectionTime)
        th = Greenlet(inp, inputs[i])
        th.start_later(0)
        ts.append(th)
    try:
        gevent.joinall(ts)
    except gevent.hub.LoopExit:
        mylog("No more msgs, exited")
        #except gevent.hub.LoopExit: pass


def broadcastClient(channels):
    # In this implementation, if a 'follower' server receives a msg from a client, it will just ignore it.
    # So a client needs to manually broadcast the msg to everyone.
    mylog("[!] Client Started...")

    def mannualBr(msg):
        mylog("[*] Doing dispatching msg:", msg)
        for channel in channels:
            channel.put(msg)  # change to asynchronous?

    mylog("[*] Broadcasting client starting...")
    mailDispatchers = []
    for i in range(MSG_TOTAL):
        t = Greenlet(mannualBr, "Message %d" % i)
        delay = random.random() * CLIENT_DELAY
        mylog(bcolors.WARNING + "\b[*] Msg dispatch %d will start in %f(s)..." % (i, delay) + bcolors.ENDC)
        t.start_later(delay)
        mailDispatchers.append(t)
    gevent.joinall(mailDispatchers)
    mannualBr("#")
    return


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-v", "--verbose", dest="verbose", default=0, type="int", help="Set verbose level",
                      metavar="VERBOSE")
    parser.add_option("-m", "--network-delay-min", dest="netmin", default=NETWORK_DELAY_MIN, type="float",
                      help="Set the min delay time of the network", metavar="TMIN")
    parser.add_option("-M", "--network-delay-max", dest="netmax", default=NETWORK_DELAY_MAX, type="float",
                      help="Set the max delay time of the network", metavar="TMAX")
    parser.add_option("-c", "--client-delay", dest="clientDelay", default=CLIENT_DELAY, type="float",
                      help="Set max delay time of the client", metavar="CLIENT_DELAY")
    parser.add_option("-n", "--message-number", dest="msgNum", default=MSG_TOTAL, type="int",
                      help="Set the number of messages", metavar="MSG_TOTAL")
    options, args = parser.parse_args()

    NETWORK_DELAY_MIN = options.netmin
    NETWORK_DELAY_MAX = options.netmax
    CLIENT_DELAY = options.clientDelay
    MSG_TOTAL = options.msgNum
    verbose = options.verbose

    def myGetTime():
        #print "[C] Now is", int(time.time() * 1000)
        #return int(time.time() * 1000) - TIME_START
        return time.time() - TIME_START

    TIME_START = myGetTime()
    mylog('[!] Initiating clients...')
    N = 10
    clientChannels = [Queue(1) for x in range(N)]
    clients = []
    clientInstance = Greenlet(broadcastClient, clientChannels)
    clientInstance.start_later(0)
    clients.append(clientInstance)
    mylog('[!] Starting raft...')
    runRaft([0] * N, clientChannels, 0, NETWORK_DELAY_MIN, NETWORK_DELAY_MAX, myGetTime)
    gevent.joinall(clients)
