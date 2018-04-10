import cPickle as pickle
import random
from base64 import encodestring

from charm.core.math.pairing import pc_element
from pytest import mark

from honeybadgerbft.crypto.threshsig.boldyreva import dealer


class TestTBLSPublicKey:

    def test_init(self, vk, vks):
        from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPublicKey
        players = 10    # TODO bind to fixtures
        count = 5   # TODO bind to fixtures
        public_key = TBLSPublicKey(players, count, vk, vks)
        assert public_key.l == players
        assert public_key.k == count
        assert public_key.VK == vk
        assert public_key.VKs == vks

    def test_getstate(self, tbls_public_key, serialized_tbls_public_key_dict):
        original_dict = tbls_public_key.__dict__.copy()
        state_dict = tbls_public_key.__getstate__()
        assert state_dict == serialized_tbls_public_key_dict
        assert tbls_public_key.__dict__ == original_dict

    def test_setstate(self, tbls_public_key, serialized_tbls_public_key_dict):
        from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPublicKey
        unset_public_key = TBLSPublicKey(None, None, None, None)
        unset_public_key.__setstate__(serialized_tbls_public_key_dict)
        assert unset_public_key.__dict__ == tbls_public_key.__dict__

    def test_pickling_and_unpickling(self, tbls_public_key):
        pickled_obj = pickle.dumps(tbls_public_key)
        unpickled_obj = pickle.loads(pickled_obj)
        assert unpickled_obj.__dict__ == tbls_public_key.__dict__


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
def test_deserialize_arg(n, g, mocker):
    from honeybadgerbft.crypto.threshsig import boldyreva
    mocked_deserialize = mocker.patch.object(
        boldyreva.group, 'deserialize', autospec=True)
    deserialize_func = getattr(boldyreva, 'deserialize{}'.format(n))
    base64_encoded_data = '{}:{}'.format(n, encodestring(g))
    deserialize_func(g)
    mocked_deserialize.assert_called_once_with(base64_encoded_data)
