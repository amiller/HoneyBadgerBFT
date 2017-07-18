#!/usr/bin/python
import gevent
from gevent import monkey
monkey.patch_all()

from gevent.queue import *
from gevent.server import StreamServer
from gevent import Greenlet
#from ..core.utils import bcolors, mylog
from collections import defaultdict
import os
import time
import socks
import struct
import math
import cPickle as pickle
import ast

from honeybadgerbft.crypto.threshsig import boldyreva
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
import rlp
from rlp.sedes import CountableList
from ethereum.transactions import Transaction

def eth_decode(payload):
    return rlp.decode(payload, CountableList(Transaction))

def eth_encode(txes):
    return rlp.encode(txes)

from subprocess import check_output
from random import Random
from socket import error as SocketError

def mylog(s, verboseLevel=0):
    print s

def to_serialized_element(x,y):
    import base64
    import binascii
    evenify = lambda x: '0' + x if len(x)%2 == 1 else x
    x = binascii.unhexlify(evenify("%x" % x))
    y = binascii.unhexlify(evenify("%x" % y))
    return "1:" + base64.b64encode(x+y)
    #return x+y

def read_keyshare_file(filename, deserialize, N=4):
    """
    This parsing routine is unique to the demo output of the DKG program.
    It returns a master VK, and a share VK for each party

    param deserialize: 
        boldyreva.group.deserialize or tpke.group.deserialize
    Return VK, VKs, SK
    """
    lines = open(filename).readlines()
    idx = 0
    while not 'Pubkey 0' in lines[idx]:
        idx += 1
    VKs = []
    for i in range(N+1):
        line = lines[idx+1+i*3]
        line = ast.literal_eval(line[2:])
        print line
        x,y = line
        VKs.append(deserialize(to_serialized_element(x,y),0))
    # second to last line is share
    SK = int(lines[-1].split(':')[-1])
    return VKs[0], VKs[1:], SK

#from ..commoncoin.boldyreva_gipc import initialize as initializeGIPC

BASE_PORT = 49500
WAITING_SETUP_TIME_IN_SEC = 3

def goodread(f, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        buf.append(f.read(ltmp))
        ltmp -= len(buf[-1])
    return ''.join(buf)

def goodrecv(sock, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        m = sock.recv(length)
        if len(m) == 0: # File closed
            assert False
        buf.append(m)
        ltmp -= len(buf[-1])
    return ''.join(buf)

def listen_to_channel(port):
    # Returns a queue we can read from
    mylog('Preparing server on %d...' % port)
    q = Queue()
    def _handle(socket, address):
        #f = socket.makefile()
        while True:
            try:
                msglength, = struct.unpack('<I', goodrecv(socket, 4))
                line = goodrecv(socket, msglength)
            except AssertionError:
                print 'Receive Failed!'
                return
            obj = decode(line)
            sender, payload = obj
            # TODO: authenticate sender using TLS certificate
            q.put( (sender, payload) )
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

def connect_to_channel(hostname, port, myID):
    # Returns a queue we can write to
    mylog('Trying to connect to %s as party %d' % (repr((hostname, port)), myID), verboseLevel=-1)
    s = socks.socksocket()
    q = Queue()
    def _run():
        retry = True
        while retry:
            try:
                s = socks.socksocket()
                s.connect((hostname, port))
                retry = False
            except Exception, e:  # socks.SOCKS5Error:
                retry = True
                gevent.sleep(1)
                s.close()
                mylog('retrying (%s, %d) caused by %s...' % (hostname, port, str(e)) , verboseLevel=-1)
        mylog('Connection established (%s, %d)' % (hostname, port))
        while True:
            obj = q.get()
            try:
                content = encode((myID,obj))
            except TypeError:
                print obj
                raise
            try:
                s.sendall(struct.pack('<I', len(content)) + content)
            except SocketError:
                print '!! [to %d] sending %d bytes' % (myID, len(content))
                break
        print 'closed channel'
    gtemp = Greenlet(_run)
    gtemp.parent_args = (hostname, port, myID)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

def exception(msg):
    mylog(bcolors.WARNING + "Exception: %s\n" % msg + bcolors.ENDC)
    os.exit(1)

def encode(m):
    return pickle.dumps(m)

def decode(s):
    return pickle.loads(s)

def run_badger_node(myID, N, f, sPK, sSK, ePK, eSK):
    '''
    Test for the client with random delay channels
    :param i: the current node index
    :param N: the number of parties
    :param t: the number of malicious parties toleranted
    :return None:
    '''
    assert type(sPK) is boldyreva.TBLSPublicKey
    assert type(sSK) is boldyreva.TBLSPrivateKey
    assert type(ePK) is tpke.TPKEPublicKey
    assert type(eSK) is tpke.TPKEPrivateKey

    # Create the listening channel
    recv_queue = listen_to_channel(BASE_PORT + myID)
    recv = recv_queue.get
    print 'server started'

    # Create the sending channels
    send_queues = []
    for i in range(N):
        port = BASE_PORT + i
        send_queues.append(connect_to_channel('127.0.0.1', port, myID))
    def send(j, obj):
        send_queues[j].put(obj)

    # Start the honeybadger instance
    tx_submit = Queue()
    tx_commit = Queue()
    hbbft = HoneyBadgerBFT("sid", myID, 8, N, f,
                           sPK, sSK, ePK, eSK,
                           send, recv,
                           tx_submit.get, tx_commit.put,
                           encode=eth_encode, decode=eth_decode)
    th = Greenlet(hbbft.run)
    th.parent_args = (N, f)
    th.name = __file__+'.honestParty(%d)' % i
    th.start()

    # Submit random transactions
    #for txidx in range(100):
    #    tx_submit.put(["Transaction:%d:%d" % (myID, txidx)])
    #    gevent.sleep(1)
    th.join()

import atexit
def exit():
    print "Entering atexit()"

if __name__ == '__main__':
    
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-i", "--index", dest="i",
                      help="Node index (1 through -N)", metavar="I", type="int")
    (options, args) = parser.parse_args()

    N = 4
    f = 1
    if not options.i:
        parser.error('Please specify the arguments')
        system.exit(1)
    assert 1 <= options.i <= 4
    myID = options.i-1
    print myID

    while True:
        try:
            sVK, sVKs, sSK = read_keyshare_file('dkg/DKG_0.8.0/DKG-Executable/ss512/node%d/keys.out'%(myID+1), tpke.group.deserialize)
            eVK, eVKs, eSK = read_keyshare_file('dkg/DKG_0.8.0/DKG-Executable/ss512/node%d/keys.out'%(myID+1), tpke.group.deserialize)
        except IOError, e:
            gevent.sleep(1) # Waiting for keys
            continue
        break
    print 'OK!'
    ePK = tpke.TPKEPublicKey(N, f+1, eVK, eVKs)
    eSK = tpke.TPKEPrivateKey(N, f+1, eVK, eVKs, eSK, myID)
    sPK = boldyreva.TBLSPublicKey(N, f+1, sVK, sVKs)
    sSK = boldyreva.TBLSPrivateKey(N, f+1, sVK, sVKs, sSK, myID)

    run_badger_node(myID, N, f, sPK, sSK, ePK, eSK)
    
