from pytest import fixture


@fixture
def ec_secret():
    return '' + \
        'a0dc65ffca799873cbea0ac274015b9526505daaaed385155425f7337704883e'


@fixture
def ec_private():
    return '308201130201010420' + \
        'a0dc65ffca799873cbea0ac274015b9526505daaaed385155425f7337704883e' + \
        'a081a53081a2020101302c06072a8648ce3d0101022100' + \
        'fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f' + \
        '300604010004010704410479be667ef9dcbbac55a06295ce870b07029bfcdb2d' + \
        'ce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a6' + \
        '8554199c47d08ffb10d4b8022100' + \
        'fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141' + \
        '020101a14403420004' + \
        '0791dc70b75aa995213244ad3f4886d74d61ccd3ef658243fcad14c9ccee2b0a' + \
        'a762fbc6ac0921b8f17025bb8458b92794ae87a133894d70d7995fc0b6b5ab90'


class TestKey(object):

    def test_generate(self, ec_secret, ec_private):
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        k = KEY()
        k.generate(ec_secret.decode('hex'))
        k.set_compressed(True)
        privkey = k.get_privkey ().encode('hex')
        pubkey = k.get_pubkey().encode('hex')
        secret = k.get_secret().encode('hex')


def test_main():
    from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import main
    main()
