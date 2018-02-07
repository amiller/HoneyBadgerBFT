import random

import gevent
from gevent import Greenlet
from gevent.queue import Queue
from pytest import mark, raises

from honeybadgerbft.core.reliablebroadcast import reliablebroadcast, encode, decode
from honeybadgerbft.core.reliablebroadcast import hash, merkleTree, getMerkleBranch, merkleVerify


### Merkle tree
def test_merkletree0():
    mt = merkleTree(["hello"])
    assert mt == ["", hash("hello")]

def test_merkletree1():
    strList = ["hello","hi","ok"]
    mt = merkleTree(strList)
    roothash = mt[1]
    assert len(mt) == 8
    for i in range(3):
        val = strList[i]
        branch = getMerkleBranch(i, mt)
        assert merkleVerify(3, val, roothash, branch, i)

### Zfec
def test_zfec1():
    K = 3
    N = 10
    m = "hello this is a test string"
    stripes = encode(K, N, m)
    assert decode(K, N, stripes) == m
    _s = list(stripes)
    # Test by setting some to None
    _s[0] = _s[1] = _s[4] = _s[5] = _s[6] = None
    assert decode(K, N, _s) == m
    _s[3] = _s[7] = None
    assert decode(K, N, _s) == m
    _s[8] = None
    with raises(ValueError) as exc:
        decode(K, N, _s)
    assert exc.value.message == 'Too few to recover'

### RBC
def simple_router(N, maxdelay=0.01, seed=None):
    """Builds a set of connected channels, with random delay
    @return (receives, sends)
    """
    rnd = random.Random(seed)
    #if seed is not None: print 'ROUTER SEED: %f' % (seed,)
    
    queues = [Queue() for _ in range(N)]
    
    def makeSend(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
            #print 'SEND %8s [%2d -> %2d] %.2f' % (o[0], i, j, delay)
            gevent.spawn_later(delay, queues[j].put, (i,o))
            #queues[j].put((i, o))
        return _send
    
    def makeRecv(j):
        def _recv():
            (i,o) = queues[j].get()
            #print 'RECV %8s [%2d -> %2d]' % (o[0], i, j)
            return (i,o)
        return _recv
        
    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])


def byzantine_router(N, maxdelay=0.01, seed=None, **byzargs):
    """Builds a set of connected channels, with random delay,
    and possibly byzantine behavior.
    """
    rnd = random.Random(seed)
    queues = [Queue() for _ in range(N)]

    def makeSend(i):
        def _send(j, o):
            delay = rnd.random() * maxdelay
            if i == byzargs.get('byznode'):
                if o[0] == byzargs.get('message_type'):
                    screwed_up = list(o)
                    if o[0] in ('VAL', 'ECHO'):
                        screwed_up[3] = 'screw it'
                    o = tuple(screwed_up)
            gevent.spawn_later(delay, queues[j].put, (i, o))
        return _send

    def makeRecv(j):
        def _recv():
            i, o = queues[j].get()
            return i ,o
        return _recv

    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])


def _test_rbc1(N=4, f=1, leader=None, seed=None):
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    sid = 'sidA'
    rnd = random.Random(seed)
    router_seed = rnd.random()
    if leader is None: leader = rnd.randint(0,N-1)
    sends, recvs = simple_router(N, seed=seed)
    threads = []
    leader_input = Queue(1)
    for i in range(N):
        input = leader_input.get if i == leader else None
        t = Greenlet(reliablebroadcast, sid, i, N, f, leader, input, recvs[i], sends[i])
        t.start()
        threads.append(t)

    m = "Hello! This is a test message."
    leader_input.put(m)
    gevent.joinall(threads)
    assert [t.value for t in threads] == [m]*N


@mark.parametrize('seed', range(20))
@mark.parametrize('N,f', ((4, 1), (5, 1), (8, 2)))
def test_rbc1(N, f, seed):
    _test_rbc1(N=N, f=f, seed=seed)


def _test_rbc2(N=4, f=1, leader=None, seed=None):
    # Crash up to f nodes
    #if seed is not None: print 'SEED:', seed
    sid = 'sidA'
    rnd = random.Random(seed)
    router_seed = rnd.random()
    if leader is None: leader = rnd.randint(0,N-1)
    sends, recvs = simple_router(N, seed=router_seed)
    threads = []
    leader_input = Queue(1)

    for i in range(N):
        input = leader_input.get if i == leader else None
        t = Greenlet(reliablebroadcast, sid, i, N, f, leader, input, recvs[i], sends[i])
        t.start()
        threads.append(t)

    m = "Hello!asdfasdfasdfasdfasdfsadf"
    leader_input.put(m)
    gevent.sleep(0)  # Let the leader get out its first message
    
    # Crash f of the nodes
    crashed = set()
    #print 'Leader:', leader
    for _ in range(f):
        i = rnd.choice(range(N))
        crashed.add(i)
        threads[i].kill()
        threads[i].join()
    #print 'Crashed:', crashed
    gevent.joinall(threads)
    for i,t in enumerate(threads):
        if i not in crashed: assert t.value == m


@mark.parametrize('seed', range(20))
@mark.parametrize('N,f', ((4, 1), (5, 1), (8, 2)))
def test_rbc2(N, f, seed):
    _test_rbc2(N=N, f=f, seed=seed)


@mark.parametrize('seed', range(20))
@mark.parametrize('tag', ('VAL', 'ECHO'))
@mark.parametrize('N,f', ((4, 1), (5, 1), (8, 2)))
def test_rbc_when_merkle_verify_fails(N, f, tag, seed):
    rnd = random.Random(seed)
    leader = rnd.randint(0, N-1)
    byznode = 1
    sends, recvs = byzantine_router(
        N, seed=seed, byznode=byznode, message_type=tag)
    threads = []
    leader_input = Queue(1)
    for pid in range(N):
        sid = 'sid{}'.format(leader)
        input = leader_input.get if pid == leader else None
        t = Greenlet(reliablebroadcast, sid, pid, N, f, leader, input, recvs[pid], sends[pid])
        t.start()
        threads.append(t)

    m = "Hello! This is a test message."
    leader_input.put(m)
    completed_greenlets = gevent.joinall(threads, timeout=0.5)
    expected_rbc_result = None if leader == byznode and tag == 'VAL' else m
    assert all([t.value == expected_rbc_result for t in threads])


# TODO: Test more edge cases, like Byzantine behavior
