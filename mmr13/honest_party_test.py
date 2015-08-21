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
#print state

nameList = ["Alice", "Bob", "Christina", "David", "Eco", "Francis", "Gerald", "Harris", "Ive", "Jessica"]

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

def randomTransaction():
    tx = Transaction()
    tx.source = random.choice(nameList)
    tx.target = random.choice(nameList)
    tx.amount = random.randint(1, 100)
    return tx

def client_test_random_delay(N, t):
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

    buffers = map(lambda _: Queue(1), range(N))
    parser = defaultdict(lambda _: lambda _: None)

    def it(tokens): # include transaction
        target = int(tokens[1])
        if len(tokens)==2:
            controlChannels[target].put(('IncludeTransaction', randomTransaction()))
        else:
            exception("Bad Arguments")
    def halt(tokens): # halt
        target = int(tokens[1])
        if len(tokens)==2:
            controlChannels[target].put(('Halt', None))
        else:
            exception("Bad Arguments")
    def msg(tokens):
        target = int(tokens[1])
        if len(tokens)==3:
            controlChannels[target].put(('Msg', tokens[2]))
        else:
            exception("Bad Arguments")
    def help(tokens):
        mylog("%s\n" % client_test_random_delay.__doc__)

    parser["it"] = parser["i"] = it
    parser["halt"] = parser["h"] = halt
    parser["msg"] = parser["m"] = msg
    parser["help"] = help

    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        def _broadcast(v):
            def _deliver(j):
                #print 'Delivering', v, 'from', i, 'to', j
                mylog(bcolors.OKGREEN + "MSG: [%d] -> [%d]: %s" % (i, j, repr(v)) + bcolors.ENDC)
                buffers[j].put((i,v))
                mylog(bcolors.OKGREEN + "     [%d] -> [%d]: Finish" % (i, j) + bcolors.ENDC)
            for j in range(N):
                Greenlet(_deliver, j).start_later(random.random()*maxdelay)
        return _broadcast

    while True:
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        for i in range(N):
            bc = makeBroadcast(i)
            recv = buffers[i].get
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))
            th.start_later(random.random() * maxdelay)
            ts.append(th)

        def monitorUserInput(): # No idea why raw_input will block the whole gevent, need some investigation
            while True:
                mylog(">>>")
                tokens = [s for s in raw_input().strip().split() if s]
                mylog("= %s\n" % repr(parser[tokens[0]](tokens)))

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)
            tokens = [s for s in raw_input().strip().split() if s]
            mylog("= %s\n" % repr(parser[tokens[0]](tokens)))  # In case the parser has an output

if __name__ == '__main__':
    client_test_random_delay(5, 1)
