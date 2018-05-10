import gevent
from ..crypto.threshenc import tpke
import os


def serialize_UVW((U, V, W)):
    # U: element of g1 (65 byte serialized for SS512)
    U = tpke.serialize(U)
    assert len(U) == 65
    # V: 32 byte str
    assert len(V) == 32
    # W: element of g2 (32 byte serialized for SS512)
    W = tpke.serialize(W)
    assert len(W) == 65
    UVW = U + V + W
    return UVW


def deserialize_UVW(UVW):
    assert len(UVW) == 65+32+65
    U = UVW[:65]
    V = UVW[65:-65]
    W = UVW[-65:]
    U = tpke.deserialize1(U)
    W = tpke.deserialize2(W)
    return (U, V, W)


def honeybadger_block(pid, N, f, PK, SK, propose_in, acs_in, acs_out, tpke_bcast, tpke_recv):
    """The HoneyBadgerBFT algorithm for a single block

    :param pid: my identifier
    :param N: number of nodes
    :param f: fault tolerance
    :param PK: threshold encryption public key
    :param SK: threshold encryption secret key
    :param propose_in: a function returning a sequence of transactions
    :param acs_in: a function to provide input to acs routine
    :param acs_out: a blocking function that returns an array of ciphertexts
    :param tpke_bcast:
    :param tpke_recv:
    :return:
    """

    # Broadcast inputs are of the form (tenc(key), enc(key, transactions))

    # Threshold encrypt
    # TODO: check that propose_in is the correct length, not too large
    prop = propose_in()
    key = os.urandom(32) # random 256-bit key
    ciphertext = tpke.encrypt(key, prop)
    tkey = PK.encrypt(key)

    import cPickle as pickle
    to_acs = pickle.dumps((serialize_UVW(tkey), ciphertext))
    acs_in(to_acs)

    # Wait for the corresponding ACS to finish
    vall = acs_out()
    assert len(vall) == N
    assert len([_ for _ in vall if _ is not None]) >= N - f  # This many must succeed

    # print pid, 'Received from acs:', vall

    # Broadcast all our decryption shares
    my_shares = []
    for i, v in enumerate(vall):
        if v is None:
            my_shares.append(None)
            continue
        (tkey, ciph) = pickle.loads(v)
        tkey = deserialize_UVW(tkey)
        share = SK.decrypt_share(tkey)
        # share is of the form: U_i, an element of group1
        my_shares.append(share)

    tpke_bcast(my_shares)

    # Receive everyone's shares
    shares_received = {}
    while len(shares_received) < f+1:
        (j, shares) = tpke_recv()
        if j in shares_received:
            # TODO: alert that we received a duplicate
            print 'Received a duplicate decryption share from', j
            continue
        shares_received[j] = shares

    assert len(shares_received) >= f+1
    # TODO: Accountability
    # If decryption fails at this point, we will have evidence of misbehavior,
    # but then we should wait for more decryption shares and try again
    decryptions = []
    for i, v  in enumerate(vall):
        if v is None: continue
        svec = {}
        for j, shares in shares_received.iteritems():
            svec[j] = shares[i] # Party j's share of broadcast i
        (tkey, ciph) = pickle.loads(v)
        tkey = deserialize_UVW(tkey)
        key = PK.combine_shares(tkey, svec)
        plain = tpke.decrypt(key, ciph)
        decryptions.append(plain)
    #print 'Done!', decryptions

    return tuple(decryptions)
