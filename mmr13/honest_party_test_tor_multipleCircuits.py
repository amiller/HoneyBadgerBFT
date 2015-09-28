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
from gevent.server import StreamServer
import fcp
import json
import cPickle as pickle
import time
import zlib
#print state
import base64
import socks

TOR_SOCKSPORT = range(9050, 9100)

def listen_to_channel(port):
    mylog('Preparing server on %d...' % port)
    q = Queue(1)
    def _handle(socket, address):
        f = socket.makefile()
        for line in f:
            #print 'line read from socket', line
            obj = decode(base64.b64decode(line))
            # mylog('decoding')
            # mylog(obj, verboseLevel=-1)
            q.put(obj[1:])
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, party):
    mylog('Trying to connect to %s for party %d' % (repr((hostname, port)), party), verboseLevel=-1)
    retry = True
    s = socks.socksocket()
    while retry:
      try:
        s = socks.socksocket()
        s.setproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", TOR_SOCKSPORT[party], True)
        s.connect((hostname, port))
        retry = False
      except Exception, e:  # socks.SOCKS5Error:
        retry = True
        s.close()
        mylog('retrying (%s, %d) caused by %s...' % (hostname, port, str(e)) , verboseLevel=-1)
    q = Queue(1)
    def _handle():
        while True:
            obj = q.get()
            retry = True
            s.sendall(base64.b64encode(encode(obj)) + '\n')
            #        retry = False
            #    except:
            #        retry = True
            #        mylog('retrying...', verboseLevel=-1)
                
    gtemp = Greenlet(_handle)
    gtemp.parent_args = (hostname, port, party)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

BASE_PORT = 49500

TOR_MAPPING_LIST = """
3lejkcwieaamk2ea.onion
l2y6c2tztpjbcjv5.onion
cystbatihmcyj6nf.onion
hhhegzzwem6v2rpx.onion
za44dm5gbhkzif24.onion
gjbcxcdek272x5kv.onion
bgge235qrp2vc67b.onion
qd5pf7tlzv7tgvfm.onion
2gexsunkq5bruu2q.onion
alh6vi2fwxobluq5.onion
f3oqs4hq6lo6a7xl.onion
5hrnuw7iz2fnfgkv.onion
ijjkdw6fnrdhgt3d.onion
l5yd4jelejc2gl3i.onion
yyrdvlvucwbig56a.onion
fpcak233m6ohegms.onion
p2wvpc3tkdfqog6j.onion
5phvu6syhjbm7n3w.onion
hcgkkdxwvsc5qswe.onion
udaba767u7aocmty.onion
75ll7ngx7e6sq6rp.onion
jyyjnevnavat3ud5.onion
rpen3n6wguukl3fr.onion
pwxrwkuhskjkf26y.onion
akkrpjhtjar7yarw.onion
ag6x77z66y55iguk.onion
pztc6izyol5w3jaj.onion
pz6ud2oybmsentni.onion
qfq2jgfh7o32k2cj.onion
u35gwataqartl2mt.onion
47jglydcvty2ajti.onion
nolmnj6sydrfjsbi.onion
w7w5dfvh7b4uhfvf.onion
6oxlexh3egtcocax.onion
uta7m36evktozfly.onion
xtq2j4o46gmk5liw.onion
weizky5fuspvvcop.onion
pksea5efjhktetyj.onion
opb6sxzwoxyiacj2.onion
ifpcfzorimmshzbr.onion
rrcb7ig6rlq4icuw.onion
klnkwktznrfd7xh7.onion
k3p7vyopsssabkf5.onion
h3jmbkx65wzhowto.onion
i2bgufwjkbnncsyc.onion
tn6km6tybxxv6xa4.onion
o7clcncv6iyssmzg.onion
oyryk4bgjj3nwbeu.onion
z2bljpd5bznkqxc5.onion
dlhjnxs5awxi5pdt.onion
btwlcctwfo5cib4m.onion
szfdodi4s5riz27o.onion
6prcdgeestfe46a3.onion
g6gz5mtn5wtmf7vy.onion
ouzen35jbwspxhw7.onion
yso3ej7dfifcpsbh.onion
yrznvdn4nlu7qqbo.onion
7nqrqtnvqrhe6lqu.onion
xv4ankt2gxiixgp4.onion
khklcuhms5nk65vy.onion
zyhrbtnimfysuj3w.onion
vqh5avrnbc55wykm.onion
icwmhirkf2dtnh6j.onion
oemvdbpphjrj3tbk.onion
h26wnqcw5v6x6yuk.onion
jjik6qz7ka4weijf.onion
cqxcbi2vepvbzh7e.onion
vmc6il7lg5hwt26p.onion
ymaoog64u7hsq5vf.onion
7wq5fmlxjejubpcg.onion
m62btnlnxfkpwhme.onion
2hdofxd47k2jqr24.onion
re7l2oe6cct7qvls.onion
pm4h7zat2427wk4p.onion
tycuewubq36yda3i.onion
3hni35xqzhmaobb7.onion
y2t3ttxksas2liv4.onion
ojodbuqpbgsnu2zm.onion
eszv35asqgniiarw.onion
ic25j4yqirfnuihw.onion
hjidbaj56budwncn.onion
z67nhcmcv64u4g5h.onion
4eit34fwfoegbjae.onion
n4tzfy6ptzdffs4o.onion
7i5zs4vxsgubooqn.onion
cq3ampvpbxlkbf4n.onion
avhbcewtfxl2mikm.onion
xbasrgkmxuehamun.onion
awxpcqfk3xq6jtkf.onion
7zk7wmijdd3rwpq2.onion
t76n3uhiunubmr65.onion
ww4jonpalspy6pq7.onion
pocfuex33tlx6p3p.onion
vnvrc2sswr25gnzx.onion
xqiba42eladeyefr.onion
qavjxdb5445wquw7.onion
xzkvmf5dmf2lq5wn.onion
7gwsdh3463dhahts.onion
2ep34mm32vx7doiw.onion
2ui2d4yzvgp2alxu.onion
""".strip().split('\n')

TOR_MAPPINGS = [(host, BASE_PORT+i) for i, host in enumerate(TOR_MAPPING_LIST)]
mylog("[INIT] TOR_MAPPINGS: %s" % repr(TOR_MAPPINGS))

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

def randomTransactionStr():
    return repr(randomTransaction())

msgCounter = 0
starting_time = dict()
ending_time = dict()
msgSize = dict()
msgFrom = dict()
msgTo = dict()
msgContent = dict()
logChannel = Queue()

def logWriter(fileHandler):
    while True:
        msgCounter, msgSize, msgFrom, msgTo, st, et, content = logChannel.get()
        fileHandler.write("%d:%d(%d->%d)[%s]-[%s]%s\n" % (msgCounter, msgSize, msgFrom, msgTo, st, et, content))
        fileHandler.flush()

def encode(m):
    global msgCounter
    msgCounter += 1
    starting_time[msgCounter] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    result = zlib.compress(
        pickle.dumps((msgCounter, m)),
    9)  # Highest compression level
    msgSize[msgCounter] = len(result)
    msgFrom[msgCounter] = m[1]
    msgTo[msgCounter] = m[0]
    msgContent[msgCounter] = m
    return result

def decode(s):
    result = pickle.loads(zlib.decompress(s))
    assert(isinstance(result, tuple))
    ending_time[result[0]] = str(time.time())  # time.strftime('[%m-%d-%y|%H:%M:%S]')
    msgContent[result[0]] = None
    logChannel.put((result[0], msgSize[result[0]], msgFrom[result[0]], msgTo[result[0]], starting_time[result[0]], ending_time[result[0]], result[1]))
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

    #buffers = map(lambda _: Queue(1), range(N))
    gtemp = Greenlet(logWriter, open('msglog.TorMultiple', 'w'))
    gtemp.parent_args = (N, t)
    gtemp.name = 'client_test_freenet.logWriter'
    gtemp.start()
    # Instantiate the "broadcast" instruction
    def makeBroadcast(i):
        chans = []
        # First establish N connections (including a self connection)
        for j in range(N):
            host, port = TOR_MAPPINGS[j]
            chans.append(connect_to_channel(host, port, i))
        def _broadcast(v):
            # mylog(bcolors.OKGREEN + "[%d] Broadcasted %s" % (i, repr(v)) + bcolors.ENDC, verboseLevel=-1)
            for j in range(N):
                chans[j].put((j, i, v))  # from i to j
        return _broadcast

    servers = []
    for i in range(N):
        _, port = TOR_MAPPINGS[i]
        servers.append(listen_to_channel(port))
    gevent.sleep(2)
    print 'servers started'

    #while True:
    if True:  # We only test for once
        initBeforeBinaryConsensus()
        ts = []
        controlChannels = [Queue() for _ in range(N)]
        bcList = dict()
        tList = []
        def _makeBroadcast(x):
            bc = makeBroadcast(x)
            bcList[x] = bc
        for i in range(N):
            tmp_t = Greenlet(_makeBroadcast, i)
            tmp_t.parent_args = (N, t)
            tmp_t.name = 'client_test_freenet._makeBroadcast(%d)' % i
            tmp_t.start()
            tList.append(tmp_t)
        gevent.joinall(tList)
        for i in range(N):
            bc = bcList[i]  # makeBroadcast(i)
            recv = servers[i].get
            th = Greenlet(honestParty, i, N, t, controlChannels[i], bc, recv)
            th.parent_args = (N, t)
            th.name = 'client_test_freenet.honestParty(%d)' % i
            # controlChannels[i].put(('IncludeTransaction', randomTransactionStr()))
            th.start()
            mylog('Summoned party %i at time %f' % (i, time.time()), verboseLevel=-1)
            ts.append(th)
        for i in range(N):
            controlChannels[i].put(('IncludeTransaction', randomTransaction()))

        #Greenlet(monitorUserInput).start()
        try:
            gevent.joinall(ts)
        except ACSException:
            gevent.killall(ts)
        except gevent.hub.LoopExit: # Manual fix for early stop
            print "Concensus Finished"
            mylog(bcolors.OKGREEN + ">>>" + bcolors.ENDC)


import GreenletProfiler
import atexit
import gc
import traceback
from greenlet import greenlet

USE_PROFILE = False


def exit():
    halfmsgCounter = 0
    for msgindex in starting_time.keys():
        if msgindex not in ending_time.keys():
            logChannel.put((msgindex, msgSize[msgindex], msgFrom[msgindex],
                            msgTo[msgindex], starting_time[msgindex], time.time(), '[UNRECEIVED]' + msgContent[msgindex]))
            halfmsgCounter += 1
    mylog('%d extra log exported.' % halfmsgCounter, verboseLevel=-1)

    for ob in gc.get_objects():
        if not isinstance(ob, greenlet):
            continue
        if not ob:
            continue
        mylog(''.join(traceback.format_stack(ob.gr_frame)), verboseLevel=-1)
    
    if USE_PROFILE:
        GreenletProfiler.stop()
        stats = GreenletProfiler.get_func_stats()
        stats.print_all()
        stats.save('profile.callgrind', type='callgrind')

if __name__ == '__main__':
    GreenletProfiler.set_clock_type('cpu')
    atexit.register(exit)
    if USE_PROFILE:
        GreenletProfiler.start()
    client_test_freenet(6, 0)

