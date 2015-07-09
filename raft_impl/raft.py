import gevent
from gevent import Greenlet
from gevent.queue import Queue
from collections import defaultdict
import random
import json

INF = 1e40
RPC_TIMEOUT = 50000
MIN_RPC_LATENCY = 10000
MAX_RPC_LATENCY = 15000
ELECTION_TIMEOUT = 100000
BATCH_SIZE = 1
RECV_TIMEOUT = 50
# The BV_Broadcast algorithm from [MMR13]
# recvClient can block
def raftServer(pid, N, t, broadcast, send, receive, recvClient, output, getTime, getElectionTimeDelay):

    def sendRequest(j, m):
        send(j, ('request', m))
    def sendResponse(j, m):
        send(j, ('response', m))
    def makeElectionTime():
        return getTime() + getElectionTimeDelay()
    def run(v):
        global pid
        # Here we just ignore the input
        state = 'follower'
        term = 1
        votedFor = None
        electionTimeout = makeElectionTime()
        voteGranted = [False]*N
        matchIndex = [0]*N
        nextIndex = [1]*N
        rpcDue = [0]*N
        log = []
        commitIndex = 0
        heartbeatDue = [0]*N
        # Setup the client-msg monitor
        def clientCallBack(msg):
            if state=='leader':
                log.append(dict(term=term, msg=msg))
            Greenlet(clientMonitor, {}).start_later(0)
            ############################## Send msg to the leader
        def clientMonitor():
            msg = recvClient()
            clientCallBack(msg)
        Greenlet(clientMonitor, {}).start_later(0)
        ##########################
        def accessLog(index):
            if index<1 or index>len(log):
                return None
            return log[index-1]
        def stepDown(newTerm):
            global term, state, votedFor, electionTimeout
            term = newTerm
            state = 'follower'
            votedFor = None
            if electionTimeout <= getTime() or electionTimeout == INF:
                electionTimeout = makeElectionTime()
        #############################
        def startNewElection():
            if (state == 'follower' or state == 'candidate') and electionTimeout <= getTime():
                global state, term, votedFor, electionTimeout, voteGranted, matchIndex, rpcDue, heartbeatDue, nextIndex
                electionTimeout = makeElectionTime()
                term += 1
                votedFor = pid
                state = 'candidate'
                voteGranted = [False]*N
                matchIndex = [0]*N
                nextIndex = [1]*N
                rpcDue = [0]*N
                heartbeatDue = [0]*N

        def sendRequestVote(j):
            if (state=='candidate' and rpcDue[j] <= getTime()):
                rpcDue[j] = getTime() + RPC_TIMEOUT
                sendRequest(j, {
                    'from':pid,
                    'to':j,
                    'type':'RequestVote',
                    'term':term,
                    'lastLogTerm':log[-1],
                    'lastLogIndex':len(log)
                })

        def count(container, value):
            return len([1 for x in container if container[x]==value])

        def becomeLeader():
            global state, nextIndex, rpcDue, heartbeatDue, electionTimeout
            if (state=='candidate' and count(voteGranted, True)+1 > N/2):
                state = 'leader'
                nextIndex = [len(log)+1]*N
                rpcDue = [INF]*N
                heartbeatDue = [0]*N
                electionTimeout = INF

        def sendAppendEntries(j):
            if (state=='leader' and
                    (heartbeatDue[j]<=getTime() or
                         (nextIndex[j] <= len(log) and rpcDue[j] <= getTime()))):
                prevIndex = nextIndex[j] - 1
                lastIndex = min(prevIndex + BATCH_SIZE, len(log))
                if (matchIndex[j] + 1 < nextIndex[j]):
                    lastIndex = prevIndex
                sendRequest(j, {
                    'from': pid,
                    'to': j,
                    'type': 'AppendEntries',
                    'term': term,
                    'prevIndex': prevIndex,
                    'prevTerm': accessLog(prevIndex),
                    'entries': log[prevIndex:lastIndex], # To create a copy
                    'commitIndex': min(commitIndex, lastIndex)
                })
                rpcDue[j] = getTime() + RPC_TIMEOUT
                heartbeatDue[j] = getTime() + ELECTION_TIMEOUT / 2

        def advanceCommitIndex():
            global commitIndex
            matchIndexArray = matchIndex[:]
            matchIndexArray[pid] = len(log)
            n = sorted(matchIndexArray)[N/2]
            if (state=='leader' and accessLog(n)['term']==term):
                commitIndex = max(commitIndex, n)

        def handleRequestVoteRequest(request):
            global votedFor, electionTimeout
            if term<request['term']:
                stepDown(request['term'])
            granted=False
            if (term == request['term'] and
                    (votedFor == None or votedFor == request['from']) and
                    (request['lastLogTerm'] > log[-1]['term'] or
                        (request['lastLogTerm'] == log[-1]['term'] and
                            request['lastLogIndex'] >= len(log)))):
                granted = True
                votedFor = request['from']
                electionTimeout = makeElectionTime()
            sendResponse(request['from'], dict(term=term, granted=granted))

        def handleRequestVoteReply(reply):
            if (term < reply['term']):
                stepDown(reply['term'])
            if (state == 'candidate' and term==reply['term']):
                rpcDue[reply['from']] = INF
                voteGranted[reply['from']] = reply['granted']

        def handleAppendEntriesRequest(req):
            global log, commitIndex, state, electionTimeout
            success = False
            matchIndex = 0
            if term < req['term']:
                stepDown(req['term'])
            if term == req['term']:
                state = 'follower'
                electionTimeout = makeElectionTime()
                if (req['prevIndex']==0 or (req['prevIndex']<len(log) and accessLog(req['prevIndex'])['term'] == req['prevTerm'])):
                    success = True
                    index = req['prevIndex']
                    for i in range(len(log)):
                        index += 1
                        if accessLog(index)!= req['entries'][i]['term']:
                            while len(log) > index - 1:
                                log.pop()
                            log.append(req['entries'][i])
                    matchIndex = index
                    commitIndex = max([commitIndex, req['commitIndex']])
            sendResponse(req['from'], dict(term=term, success=success, matchIndex=matchIndex))

        def handleAppendEntriesReply(rep):
            if term < rep['term']:
                stepDown(rep['term'])
            if state == 'leader' and term==rep['term']:
                if rep['success']:
                    matchIndex[rep['from']] = max(matchIndex[rep['from']], rep['matchIndex'])
                    nextIndex[rep['from']] = rep['matchIndex'] + 1
                else:
                    nextIndex[rep['from']] = max([1, nextIndex[rep['from']]-1])
            rpcDue[rep['from']] = 0

        def handleMessage(packedMsg):
            if state == 'stopped':
                return
            direction, msg=packedMsg
            if msg['type'] == 'requestVote':
                if direction == 'request':
                    handleRequestVoteRequest(msg)
                else:
                    handleRequestVoteReply(msg)
            elif msg['type'] == 'AppendEntries':
                if direction == 'request':
                    handleAppendEntriesRequest(msg)
                else:
                    handleAppendEntriesReply(msg)

        while True:
            global pid
            startNewElection()
            becomeLeader()
            advanceCommitIndex()
            for i in range(N):
                if i != pid:
                    sendRequestVote(i)
                    sendAppendEntries(i)
            result = receive(timeout=RECV_TIMEOUT)
            if result:
                senderID, packedMSG = result
                handleMessage(packedMSG)

    return run

# clientsChannel = map(lambda _: Queue(1), inputs)
# timeOut is a function provides a timeout like Javascript
# Run the protocol with no corruptions, uniform random message delays
def runRaft(inputs, clientsChannel, t, tMin, tMax, getTime): # Everyone broadcasts a msg in different delay

    N = len(inputs)
    buffers = map(lambda _: Queue(1), inputs)


    # Instantiate the "broadcast" instruction for node i
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                buffers[j].put((i,v))
            for j in range(N):
                Greenlet(_deliver, j).start_later(tMin + random.random()*(tMax-tMin))
        return _broadcast

    def makeSend(i):
        def _send(j,v):
            buffers[j].put((i,v))
        return _send

    def makeReceiveFromClient(i):
        return clientsChannel[i].get

    def makeOutput(i):
        def _output(v):
            print '[%d]' % (i, 'output:', v)
        return _output

    def makeReceive(i):
        return buffers[i].get
    def getElectionTime():
        return tMin + random.random()*(tMax-tMin)
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
    except gevent.hub.LoopExit: pass

if __name__ == '__main__':
    import time
    def myGetTime():
        return int(time.time() * 1000)
    runRaft([0]*5, [Queue(1) for x in range(5)], 0, 100, 200, myGetTime)