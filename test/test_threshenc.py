import unittest
from charm.toolbox.pairinggroup import PairingGroup,ZR,G1,G2,GT,pair
import random
from honeybadgerbft.crypto.threshenc.tpke import TPKEPublicKey, TPKEPrivateKey, dealer
from Crypto.Hash import SHA256
from Crypto import Random
from Crypto.Cipher import AES

def test_threshenc():
    PK, SKs = dealer(players=100,k=35)

    m = SHA256.new('hello world').digest()
    C = PK.encrypt(m)

    assert PK.verify_ciphertext(C)

    shares = [sk.decrypt_share(C) for sk in SKs]
    for i,share in enumerate(shares):
        assert PK.verify_share(i, share, C)

    SS = range(PK.l)
    for i in range(1):
        random.shuffle(SS)
        S = set(SS[:PK.k])
        
        m_ = PK.combine_shares(C, dict((s,shares[s]) for s in S))
        assert m_ == m

def test_threshenc2():
    # Failure cases
    PK, SKs = dealer(players=100,k=35)

    m = SHA256.new('hello world').digest()
    C = PK.encrypt(m)

    assert PK.verify_ciphertext(C)

    shares = [sk.decrypt_share(C) for sk in SKs]
    for i,share in enumerate(shares):
        assert PK.verify_share(i, share, C)

    SS = range(PK.l)
    random.shuffle(SS)
    # Perturb one of the keys
    shares[SS[0]] += shares[SS[0]]
    S = set(SS[:PK.k])
    
    try:
        m_ = PK.combine_shares(C, dict((s,shares[s]) for s in S))
        assert m_ == m
    except AssertionError: pass
    else: assert False, "Combine shares should have raised an error"
