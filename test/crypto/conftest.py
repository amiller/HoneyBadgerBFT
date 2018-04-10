from charm.toolbox.pairinggroup import PairingGroup, ZR, G2
from pytest import fixture


@fixture
def pairing_group_MNT224():
    return PairingGroup('MNT224')

@fixture
def pairing_group_SS512():
    return PairingGroup('SS512')


@fixture
def pairing_group(request):
    curve = request.param
    return PairingGroup(curve)


@fixture
def g():
    return (
        'm\n\x9f\xcc\xb8\xd9(4\x07\xee\xcd\xdeF\xf9\x14\x1c^\\&\x02\xff'
        '\xbd\x8e\xaa\x99\xe9b{\xb7\xa1\xa2\x90&hA\xe7\xf0\xc69\x139\xcc'
        '\xd4\xfbz\xcd\xd1\x14 {\x88w\x11\xae\x04&k2\xeea\x8f\xbe\x91W\x00'
    )


@fixture
def g2_mnt224(pairing_group_MNT224):
    g2 = pairing_group_MNT224.hash('geng2', G2)
    g2.initPP()
    return g2


@fixture(params=({'count': 5, 'seed': None},))
def polynomial_coefficients(request, pairing_group_MNT224):
    return pairing_group_MNT224.random(ZR, **request.param)


@fixture(params=(10,))
def sks(request, polynomial_coefficients):
    from honeybadgerbft.crypto.threshsig.boldyreva import polynom_eval
    players = request.param
    return [polynom_eval(i, polynomial_coefficients)
            for i in range(1, players+1)]


@fixture
def vk(g2_mnt224, polynomial_coefficients):
    return g2_mnt224 ** polynomial_coefficients[0]


@fixture
def vks(g2_mnt224, sks):
    return [g2_mnt224 ** sk for sk in sks]


@fixture
def tbls_public_key(vk, vks):
    from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPublicKey
    players = 10    # TODO bind to fixtures
    count = 5   # TODO bind to fixtures
    return TBLSPublicKey(players, count, vk, vks)


@fixture
def tbls_private_keys(vk, vks, sks):
    from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPrivateKey
    players = 10    # TODO bind to fixtures
    count = 5   # TODO bind to fixtures
    return [TBLSPrivateKey(players, count, vk, vks, sk, i)
            for i, sk in enumerate(sks)]


@fixture
def serialized_tbls_public_key_dict(tbls_public_key):
    from honeybadgerbft.crypto.threshsig.boldyreva import serialize
    return {
        'l': tbls_public_key.l,
        'k': tbls_public_key.k,
        'VK': serialize(tbls_public_key.VK),
        'VKs': map(serialize, tbls_public_key.VKs),
    }
