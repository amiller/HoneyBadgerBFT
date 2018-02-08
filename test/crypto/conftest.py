from charm.toolbox.pairinggroup import PairingGroup
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
