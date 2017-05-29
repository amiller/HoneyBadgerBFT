import random
from crypto.threshsig.boldyreva import dealer

def test_boldyreva():
    global PK, SKs
    PK, SKs = dealer(players=16,k=5)

    global sigs,h
    sigs = {}
    h = PK.hash_message('hi')
    h.initPP()

    for SK in SKs:
        sigs[SK.i] = SK.sign(h)

    SS = range(PK.l)
    for i in range(10):
        random.shuffle(SS)
        S = set(SS[:PK.k])
        sig = PK.combine_shares(dict((s,sigs[s]) for s in S))
        assert PK.verify_signature(sig, h)
