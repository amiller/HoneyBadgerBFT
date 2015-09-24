#!/usr/bin/python
__author__ = 'aluex'

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
import xmlrpclib
import time
import json
import pickle
import zlib
import base64
#print state

nameList = ["Alice", "Bob", "Christina", "David", "Eco", "Francis", "Gerald", "Harris", "Ive", "Jessica"]

SLEEP_TIME = 1
# CONCURRENT_NUM = 2
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

# def encode(m):
#    return zlib.compress(pickle.dumps(m), 9)

# def decode(s):
    # mylog('decoding %s' % repr(s))
    #if True:
#    try:
#        result = pickle.loads(zlib.decompress(s))
#    except:
#        result = None
#    return result

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
    starting_time[msgCounter] = str(time.time())  #time.strftime('[%m-%d-%y|%H:%M:%S]')
    result = zlib.compress(
        pickle.dumps((msgCounter, m)),
        9)  # Highest compression level
    msgSize[msgCounter] = len(result)
    return result


def decode(s):
    result = pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  #time.strftime('[%m-%d-%y|%H:%M:%S]')
    logChannel.put((result[0], msgSize[result[0]], starting_time[result[0]], ending_time[result[0]], result[1]))
    return result[1]


def trashAllMessages(N):
    bitmessageServers = [('127.0.0.1', 8545+x) for x in range(N)]  # From 8337, 8338, ...
    apis = [xmlrpclib.ServerProxy("http://user:badger@%s:%d" % (_[0], _[1])) for _ in bitmessageServers]
    for api in apis:
        msgs = json.loads(api.getAllInboxMessageIDs())['inboxMessageIds']
        for msg in msgs:
            api.trashMessage(msg['msgid'])
    mylog('Done with trashing.')


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
    assert(8445 + N < 8545)
    Greenlet(logWriter, open('msglog.BitmessageBroadcast', 'w')).start()

    bitmessageServers = [('127.0.0.1', 8545+x) for x in range(N)]  # From 8337, 8338, ...

    api = [xmlrpclib.ServerProxy("http://user:badger@%s:%d" % (_[0], _[1])) for _ in bitmessageServers]
    api_Read = [xmlrpclib.ServerProxy("http://user:badger@%s:%d" % (_[0], _[1])) for _ in bitmessageServers]
    mylog("Generating addresses...")
    address = []
    for i in range(N):  # In case we run it for the first time
        mylog('Creating address for %d..' % i)
        api[i].createDeterministicAddresses(base64.b64encode('123'), 1)
    for i in range(N):
        address.append([m['address'] for m in json.loads(api[i].listAddresses())['addresses']][-1])
        # listAddresses here instead of listAddresses2 ** The 0.4.4 version is not compatible with 0.4 !!!
    mylog('Got addresses :%s' % repr(address))
    mylog('Creating subscription...')
    for i in range(N):
        for j, addr in enumerate(address):
            api[i].addSubscription(addr, base64.b64encode(str(j)))

    recvChannel = [Queue() for _ in range(N)]
    def makeBroadcast(i):
        broadcastChannel = Queue()
        def _deliver(j, v):
            recvChannel[j].put((i, v))
        def _broadcastDealer():  # We have to make sure that at any time, there is only 1 instance of api[i] working
            while True:
                v = broadcastChannel.get()
                api[i].sendBroadcast(address[i], base64.b64encode('badger'),
                    base64.b64encode('HB-' + base64.b64encode(encode(v))))
        Greenlet(_broadcastDealer).start()
        def _broadcast(v):
            broadcastChannel.put(v)
            # Also we need to send to ourself
            Greenlet(_deliver, i, v).start()  # Can be start_later()
        return _broadcast

    def makeListen(i):
        def Listener():
            while True:
                gevent.sleep(SLEEP_TIME)
                msgs = json.loads(api_Read[i].getAllInboxMessages())['inboxMessages']
                for msg in msgs:
                    receipt_no = i  # address.index(msg['toAddress'])
                    tmpvar = base64.b64decode(msg['message'])
                    if tmpvar[:3] == 'HB-':
                        result = decode(
                            base64.b64decode(
                                tmpvar[3:]
                            )
                        )
                        if result:
                            mylog('[%d] got message %s' % (receipt_no, result))
                            recvChannel[receipt_no].put((
                                address.index(msg['fromAddress']), result
                            ))
                    api_Read[i].trashMessage(msg['msgid'])

        Greenlet(Listener).start()
        def _recv():
            return recvChannel[i].get()
        return _recv

    while True:
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = makeListen(i)
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            # controlChannels[i].put(('IncludeTransaction', randomTransactionStr()))
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

    #   shutdownNodes()

if __name__ == '__main__':
    # utils.verbose = -1
    trashAllMessages(10)
    client_test_freenet(10, 2)
