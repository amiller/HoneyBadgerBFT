#!/usr/bin/python
__author__ = 'aluex'
from gevent import monkey
monkey.patch_all()

from gevent.queue import Queue
from gevent import Greenlet
from utils import bcolors, mylog
from includeTransaction import honestParty, Transaction
from collections import defaultdict
from bkr_acs import initBeforeBinaryConsensus
from utils import ACSException
import gevent
import os
#import random
from utils import myRandom as random
import fcp
import json
import pickle
import time
import zlib
#print state

nameList = ["Alice", "Bob", "Christina", "David", "Eco", "Francis", "Gerald", "Harris", "Ive", "Jessica"]

CONCURRENT_NUM = 2
# CONCURRENT = True

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

def randomTransaction():
    tx = Transaction()
    tx.source = random.choice(nameList)
    tx.target = random.choice(nameList)
    tx.amount = random.randint(1, 100)
    return tx

def randomTransactionStr():
    return repr(randomTransaction())

publicKeys = []
USKPublicKeys = []
nodeList = []

def generateFreenetKeys(N):
    global publicKeys, nodeList
    mylog("Initiating ...")
    privateList = []
    USKPrivateList = []
    jobList = []
    for i in range(N * CONCURRENT_NUM):
        mylog("Registering node %d" % i)
        n = fcp.node.FCPNode()
        public, private = n.genkey()
        USKPublic, USKPrivate = n.genkey(name='badger', usk=True)
        mylog("Got public key %s, private key %s, USKPublic key %s, USKPrivate key %s" % (
            public, private, USKPublic, USKPrivate))
        mylog("Initializing msg_count for node %d" % i)
        # Set the initial counter
        j = n.put(uri=USKPrivate, data="0",
            mimetype="application/octet-stream", realtime=True, priority=0, async=True)
        jobList.append(j)
        # Update the lists
        publicKeys.append(public)
        USKPublicKeys.append(USKPublic)
        privateList.append(private)
        USKPrivateList.append(USKPrivate)
        nodeList.append(n)
    for index, job in enumerate(jobList):
        job.wait()
        mylog("Finished msg_count for node %d" % index)
    return privateList, USKPrivateList

def shutdownNodes(nodeList):
    for node in nodeList:
        node.shutdown()

msgCounter = 0
starting_time = dict()
ending_time = dict()
msgSize = dict()
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, st, et, content = logChannel.get()
        fileHandler.write("%d:%d[%s]-[%s]%s\n" % (msgCounter, msgSize, st, et, content))
        fileHandler.flush()

def encode(m):
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    result = zlib.compress(
        pickle.dumps((msgCounter, m)),
    9)  # Highest compression level
    msgSize[msgCounter] = len(result)
    return result

def decode(s):
    result = pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    logChannel.put((result[0], msgSize[result[0]], starting_time[result[0]], ending_time[result[0]], result[1]))
    return result[1]

def client_test_freenet(N, t):
    '''
    Test for the client with random delay channels

    command list
        i [target]: send a transaction to include for some particular party
        h [target]: stop some particular party
        m [target]: manually make particular party send some message
        help: show the help screen

    :param N: the number of parties
    :param t: the number of malicious parties
    :return None:
    '''
    maxdelay = 0.01
    global publicKeys, nodeList
    privateList, USKPrivateList = generateFreenetKeys(N)
    Greenlet(logWriter, open('msglog', 'w')).start()
    #buffers = map(lambda _: Queue(1), range(N))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        counter = [0] * (N * CONCURRENT_NUM)
        workchannel = Queue()
        def writeWorker(workno):
            actuall_i = CONCURRENT_NUM * i + workno
            while True:
                message = workchannel.get()
                counter[actuall_i] += 1
                mylog("[%d] writing msg %s..." % (i, repr(message)))
                nodeList[actuall_i].put(uri=privateList[actuall_i] + str(counter[actuall_i]), data=encode(message),
                                mimetype="application/octet-stream", realtime=True, priority=0)
                mylog("[%d] Updating msg_counter[%d] to %d..." % (i, workno, counter[actuall_i]))
                nodeList[actuall_i].put(uri=USKPrivateList[actuall_i], #.replace('/0', '/'+str(counter[i])),
                                data=str(counter[actuall_i]),
                                mimetype="application/octet-stream", realtime=True, priority=0)
        for x in range(CONCURRENT_NUM):
            Greenlet(writeWorker, x).start()
        def _broadcast(v):
            workchannel.put(v)
        return _broadcast

    def makeListen(i):
        recvChannel = Queue()
        recvCounter = [0] * (N * CONCURRENT_NUM)
        def listener(j, recvCounter):
            while True:
                # mylog("[%d] Updating msg_counter of %d..." % (i, j))
                uskjob = nodeList[i].get(uri=USKPublicKeys[j],
                                         async=True, realtime=True, priority=2, followRedirect=True)
                # The reason I use async here is that from the tutorial it is said this would be faster
                mime, data, meta = uskjob.wait()
                newestNum = int(data)
                if newestNum > recvCounter[j]:
                    mylog("[%d] found msg_counter[%d] of %d is %d..." % (
                        i, j % CONCURRENT_NUM, j / CONCURRENT_NUM, newestNum))
                    for c in range(recvCounter[j], newestNum):
                        job = nodeList[i].get(uri=publicKeys[j]+str(c+1),
                                              async=True, realtime=True, priority=0)
                        mime, data, meta = job.wait()
                        #recvCounter[j] += 1
                        recvChannel.put((j / CONCURRENT_NUM, decode(data)))
                    recvCounter[j] = newestNum
        for k in range(N * CONCURRENT_NUM):
            Greenlet(listener, k, recvCounter).start()
        def _recv():
            return recvChannel.get()
        return _recv

    #while True:
    if True: # We only test for once
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = makeListen(i)
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            #controlChannels[i].put(('IncludeTransaction', randomTransactionStr()))
            th.start_later(random.random() * maxdelay)
            ts.append(th)

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)

    shutdownNodes()

if __name__ == '__main__':
    client_test_freenet(5, 1)
