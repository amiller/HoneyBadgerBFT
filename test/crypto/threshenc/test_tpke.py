from base64 import decodestring
from random import shuffle

from Crypto.Hash import SHA256
from charm.toolbox.pairinggroup import PairingGroup, ZR, G1, G2, pair


def test_tpke():
    from honeybadgerbft.crypto.threshenc.tpke import dealer
    PK, SKs = dealer(players=100, k=35)

    m = SHA256.new('how').digest()
    C = PK.encrypt(m)

    assert PK.verify_ciphertext(C)

    shares = [sk.decrypt_share(C) for sk in SKs]
    for i, share in enumerate(shares):
        assert PK.verify_share(i, share, C)

    SS = range(PK.l)
    for i in range(1):
        shuffle(SS)
        S = set(SS[:PK.k])
        m_ = PK.combine_shares(C, dict((s, shares[s]) for s in S))
        assert m_ == m


def test_ciphertext_generation():
    from honeybadgerbft.crypto.threshenc.tpke import TPKEPublicKey
    players = 10
    k = 5
    group = PairingGroup('SS512')
    ZERO = group.random(ZR)*0
    ONE = group.random(ZR)*0 + 1
    g1 = group.hash('geng1', G1)
    g1.initPP()
    g2 = g1

    coefficients = [group.random(ZR) for _ in range(k)]
    secret = coefficients[0]

    # Polynomial evaluation
    def f(x):
        y = ZERO
        xx = ONE
        for coeff in coefficients:
            y += coeff * xx
            xx *= x
        return y

    # Shares of master secret key
    SKs = [f(i) for i in range(1, players+1)]
    assert f(0) == secret

    # Verification keys
    VK = g2 ** secret
    VKs = [g2 ** xx for xx in SKs]

    public_key = TPKEPublicKey(players, k, VK, VKs)
    public_key.encrypt
    message = SHA256.new('abc123').digest()
    ciphertext = public_key.encrypt(message)
    U, V, W = ciphertext

    assert len(V) == 32
    UV = decodestring(group.serialize(U)[2:]) + V
    H = group.hash(UV, G2)
    assert pair(g1, W) == pair(U, H)
