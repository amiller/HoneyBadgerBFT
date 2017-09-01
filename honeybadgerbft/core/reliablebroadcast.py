# coding=utf-8
from collections import defaultdict
import zfec
import hashlib
import math

#### zfec encode ####
def encode(K, N, m):
    """Erasure encodes string ``m`` into ``N`` blocks, such that any ``K``
    can reconstruct.

    :param int K: K
    :param int N: number of blocks to encode string ``m`` into.
    :param int m: string to encode.

    :return list: Erasure codes resulting from encoding ``m`` into
        ``N`` blocks using ``zfec`` lib.

    """
    encoder = zfec.Encoder(K, N)
    assert K <= 256  # TODO: Record this assumption!
    # pad m to a multiple of K bytes
    padlen = K - (len(m) % K)
    m += padlen * chr(K-padlen)
    step = len(m)/K
    blocks = [m[i*step : (i+1)*step] for i in range(K)]
    stripes = encoder.encode(blocks)
    return stripes

def decode(K, N, stripes):
    """Decodes an erasure-encoded string from a subset of stripes

    :param list stripes: a container of :math:`N` elements,
        each of which is either a string or ``None``
        at least :math:`K` elements are strings
        all string elements are the same length

    """
    assert len(stripes) == N
    blocks = []
    blocknums = []
    for i,block in enumerate(stripes):
        if block is None: continue
        blocks.append(block)
        blocknums.append(i)
        if len(blocks) == K: break
    else: raise ValueError("Too few to recover")
    decoder = zfec.Decoder(K, N)
    rec = decoder.decode(blocks, blocknums)
    m = ''.join(rec)
    padlen = K - ord(m[-1])
    m = m[:-padlen]
    return m

#### Merkle tree ####
def hash(x):
    assert type(x) is str
    return hashlib.sha256(x).digest()

def ceil(x): return int(math.ceil(x))

def merkleTree(strList):
    """Builds a merkle tree from a list of :math:`N` strings (:math:`N`
    at least 1)

    :return list: Merkle tree, a list of ``2*ceil(N)`` strings. The root
         digest is at ``tree[1]``, ``tree[0]`` is blank.

    """
    N = len(strList)
    assert N >= 1
    bottomrow = 2 ** ceil(math.log(N, 2))
    mt = [""] * (2 * bottomrow)
    for i in range(N):
        mt[bottomrow + i] = hash(strList[i])
    for i in range(bottomrow - 1, 0, -1):
        mt[i] = hash(mt[i*2] + mt[i*2+1])
    return mt

def getMerkleBranch(index, mt):
    """Computes a merkle tree from a list of leaves.
    """
    res = []
    t = index + (len(mt) >> 1)
    while t > 1:
        res.append(mt[t ^ 1])  # we are picking up the sibling
        t /= 2
    return res

def merkleVerify(N, val, roothash, branch, index):
    """Verify a merkle tree branch proof
    """
    assert 0 <= index < N
    assert type(val) is str
    assert len(branch) == ceil(math.log(N, 2))
    # Index has information on whether we are facing a left sibling or a right sibling
    tmp = hash(val)
    tindex = index
    for br in branch:
        tmp = hash((tindex & 1) and br + tmp or tmp + br)
        tindex >>= 1
    if tmp != roothash:
        print "Verification failed with", hash(val), roothash, branch, tmp == roothash
        return False
    return True


def reliablebroadcast(sid, pid, N, f, leader, input, receive, send):
    """Reliable broadcast

    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: ``0 <= leader < N``
    :param input: if ``pid == leader``, then :func:`input()` is called
        to wait for the input value
    :param receive: :func:`receive()` blocks until a message is
        received; message is of the form::

            (i, (tag, ...)) = receive()

        where ``tag`` is one of ``{"VAL", "ECHO", "READY"}``
    :param send: sends (without blocking) a message to a designed
        recipient ``send(i, (tag, ...))``

    :return str: ``m`` after receiving :math:`2f+1` ``READY`` messages
        and :math:`N-2f` ``ECHO`` messages

        .. important:: **Messages**

            ``VAL( roothash, branch[i], stripe[i] )``
                sent from ``leader`` to each other party
            ``ECHO( roothash, branch[i], stripe[i] )``
                sent after receiving ``VAL`` message
            ``READY( roothash )``
                sent after receiving :math:`N-f` ``ECHO`` messages
                or after receiving :math:`f+1` ``READY`` messages

    .. todo::
        **Accountability**

        A large computational expense occurs when attempting to
        decode the value from erasure codes, and recomputing to check it
        is formed correctly. By transmitting a signature along with
        ``VAL`` and ``ECHO``, we can ensure that if the value is decoded
        but not necessarily reconstructed, then evidence incriminates
        the leader.

    """
    assert N >= 3*f + 1
    assert f >= 0
    assert 0 <= leader < N
    assert 0 <= pid    < N

    K               = N - 2 * f  # Need this many to reconstruct
    EchoThreshold   = N - f      # Wait for this many ECHO to send READY
    ReadyThreshold  = f + 1      # Wait for this many READY to amplify READY
    OutputThreshold = 2 * f + 1  # Wait for this many READY to output
    # NOTE: The above thresholds  are chosen to minimize the size
    # of the erasure coding stripes, i.e. to maximize K.
    # The following alternative thresholds are more canonical
    # (e.g., in Bracha '86) and require larger stripes, but must wait
    # for fewer nodes to respond
    #   EchoThreshold = ceil((N + f + 1.)/2)
    #   K = EchoThreshold - f

    def broadcast(o):
        for i in range(N): send(i, o)

    if pid == leader:
        # The leader erasure encodes the input, sending one strip to each participant
        m = input()  # block until an input is received
        assert type(m) is str
        #print 'Input received: %d bytes' % (len(m),)

        stripes = encode(K, N, m)
        mt = merkleTree(stripes)  # full binary tree
        roothash = mt[1]

        for i in range(N):
            branch = getMerkleBranch(i, mt)
            send(i, ('VAL', roothash, branch, stripes[i]))

    # TODO: filter policy: if leader, discard all messages until sending VAL

    fromLeader = None
    stripes = defaultdict(lambda: [None for _ in range(N)])
    echoCounter = defaultdict(lambda: 0)
    echoSenders = set()  # Peers that have sent us ECHO messages
    ready = defaultdict(set)
    readySent = False
    readySenders = set()  # Peers that have sent us READY messages

    def decode_output(roothash):
        # Rebuild the merkle tree to guarantee decoding is correct
        m = decode(K, N, stripes[roothash])
        _stripes = encode(K, N, m)
        _mt = merkleTree(_stripes)
        _roothash = _mt[1]
        # TODO: Accountability: If this fails, incriminate leader
        assert _roothash == roothash
        return m

    while True:  # main receive loop
        sender, msg = receive()
        if msg[0] == 'VAL' and fromLeader is None:
            # Validation
            (_, roothash, branch, stripe) = msg
            if sender != leader:
                print "VAL message from other than leader:", sender
                continue
            try: assert merkleVerify(N, stripe, roothash, branch, pid)
            except Exception, e:
                print "Failed to validate VAL message:", e
                continue

            # Update
            fromLeader = roothash
            broadcast(('ECHO', roothash, branch, stripe ))

        elif msg[0] == 'ECHO':
            (_, roothash, branch, stripe) = msg
            # Validation
            if roothash in stripes and stripes[roothash][sender] is not None \
               or sender in echoSenders:
                print "Redundant ECHO"
                continue
            try: assert merkleVerify(N, stripe, roothash, branch, sender)
            except e:
                print "Failed to validate ECHO message:", e
                continue

            # Update
            stripes[roothash][sender] = stripe
            echoSenders.add(sender)
            echoCounter[roothash] += 1

            if echoCounter[roothash] >= EchoThreshold and not readySent:
                readySent = True
                broadcast(('READY', roothash))

            if len(ready[roothash]) >= OutputThreshold and echoCounter[roothash] >= K:
                return decode_output(roothash)

        elif msg[0] == 'READY':
            (_, roothash) = msg
            # Validation
            if sender in ready[roothash] or sender in readySenders:
                print "Redundant READY"
                continue

            # Update
            ready[roothash].add(sender)
            readySenders.add(sender)

            # Amplify ready messages
            if len(ready[roothash]) >= ReadyThreshold and not readySent:
                readySent = True
                broadcast(('READY', roothash))

            if len(ready[roothash]) >= OutputThreshold and echoCounter[roothash] >= K:
                return decode_output(roothash)
