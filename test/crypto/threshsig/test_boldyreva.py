import random
from base64 import encodestring
from importlib import import_module

from pytest import mark

from honeybadgerbft.crypto.threshsig.boldyreva import dealer


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


@mark.parametrize('n', (0, 1, 2))
@mark.parametrize('pairing_group', ('MNT224',), indirect=('pairing_group',))
def test_deserialize(pairing_group, n, g):
    from honeybadgerbft.crypto.threshsig import boldyreva
    deserialize_func = getattr(boldyreva, 'deserialize{}'.format(n))
    base64_encoded_data = '{}:{}'.format(n, encodestring(g))
    assert (deserialize_func(g) ==
            pairing_group.deserialize(base64_encoded_data))
