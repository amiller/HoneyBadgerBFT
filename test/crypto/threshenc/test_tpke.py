from base64 import encodestring, decodestring
from random import shuffle

from Crypto.Hash import SHA256
from charm.toolbox.pairinggroup import PairingGroup, ZR, G1, G2, pair
from pytest import mark


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


def test_xor():
    from honeybadgerbft.crypto.threshenc.tpke import xor
    x = ('l\xa1=R\xcap\xc8\x83\xe0\xf0\xbb\x10\x1eBZ\x89'
         '\xe8bM\xe5\x1d\xb2\xd29%\x93\xafj\x84\x11\x80\x90')
    y = ('\xb2\xdf\xfeQ3 J7H\xe8yU6S\x05zU\x85\xd3'
         '\xc1o\xa8E\xa9\xef\x02\x98\x05\xe46\xbf\x9c')
    expected_result = ("\xde~\xc3\x03\xf9P\x82\xb4\xa8\x18\xc2E(\x11_"
                       "\xf3\xbd\xe7\x9e$r\x1a\x97\x90\xca\x917o`'?\x0c")
    assert xor(x, y) == expected_result


@mark.parametrize('n', (0, 1, 2))
@mark.parametrize('pairing_group', ('SS512',), indirect=('pairing_group',))
def test_deserialize(pairing_group, n, g):
    from honeybadgerbft.crypto.threshenc import tpke
    deserialize_func = getattr(tpke, 'deserialize{}'.format(n))
    base64_encoded_data = '{}:{}'.format(n, encodestring(g))
    assert (deserialize_func(g) ==
            pairing_group.deserialize(base64_encoded_data))
