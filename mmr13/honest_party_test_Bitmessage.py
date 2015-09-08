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

def encode(m):
    return zlib.compress(pickle.dumps(m), 9)

def decode(s):
    # mylog('decoding %s' % repr(s))
    #if True:
    try:
        result = pickle.loads(zlib.decompress(s))
    except:
        result = None
    return result

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

    api = [xmlrpclib.ServerProxy("http://user:pass@127.0.0.1:8442") for _ in range(N * CONCURRENT_NUM +1)]
    mylog("Generating addresses...")
    address = [ m['address'] for m in json.loads(api[0].listAddresses2())['addresses']]
    mylog('Got addresses :%s' % repr(address))

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        workchannel = Queue()
        def writeWorker(workno):
            actuall_i = CONCURRENT_NUM * i + workno
            while True:
                message = workchannel.get()
                mylog("[%d] writing msg %s..." % (i, repr(encode(message))))
                for k in range(N):
                    target = k * CONCURRENT_NUM + random.randint(0, CONCURRENT_NUM - 1)
                    api[actuall_i].sendMessage(address[target], address[actuall_i],
                                    base64.b64encode('badger'), base64.b64encode('HB-' + base64.b64encode(encode(message))))
        for x in range(CONCURRENT_NUM):
            Greenlet(writeWorker, x).start()
        def _broadcast(v):
            workchannel.put(v)
        return _broadcast

    recvChannel = [Queue() for _ in range(N)]

    def Listener():
        while True:
            gevent.sleep(SLEEP_TIME)
            msgs = json.loads(api[N * CONCURRENT_NUM].getAllInboxMessages())['inboxMessages']
            for msg in msgs:
                receipt_no = address.index(msg['toAddress'])
                tmpvar = base64.b64decode(msg['message'])
                if tmpvar[:3] == 'HB-':
                    result = decode(
                        base64.b64decode(
                            tmpvar[3:]
                        )
                    )
                    if result:
                        mylog('[%d] got message %s' % (receipt_no / CONCURRENT_NUM, result))
                        recvChannel[receipt_no / CONCURRENT_NUM].put((
                            address.index(msg['fromAddress']) / CONCURRENT_NUM, result
                        ))
                api[N].trashMessage(msg['msgid'])

    Greenlet(Listener).start()

    def makeListen(i):
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

    #   shutdownNodes()

if __name__ == '__main__':
    client_test_freenet(5, 1)
