from random import shuffle

from Crypto.Hash import SHA256


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
