from pytest import fixture, mark, raises


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


@fixture
def pubkey():
    return '020791dc70b75aa995213244ad3f4886d74d61ccd3ef658243fcad14c9ccee2b0a'


@fixture
def privkey():
    return ('3081d30201010420a0dc65ffca799873cbea0ac274015b9526505daaaed38515'
            '5425f7337704883ea08185308182020101302c06072a8648ce3d0101022100ff'
            'fffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f30'
            '0604010004010704210279be667ef9dcbbac55a06295ce870b07029bfcdb2dce'
            '28d959f2815b16f81798022100fffffffffffffffffffffffffffffffebaaedc'
            'e6af48a03bbfd25e8cd0364141020101a124032200020791dc70b75aa9952132'
            '44ad3f4886d74d61ccd3ef658243fcad14c9ccee2b0a')


@fixture
def pubkey_bytes(pubkey):
    return pubkey.decode('hex')


@fixture
def privkey_bytes(privkey):
    return privkey.decode('hex')


class TestKey(object):

    def test_del(self, mocker):
        from honeybadgerbft.crypto.ecdsa import ecdsa_ssl
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        mocked_ssl = mocker.patch.object(ecdsa_ssl, 'ssl')
        key = KEY()
	k_before_del = key.k
        key.__del__()
        mocked_ssl.EC_KEY_free.assert_called_once_with(k_before_del)
	assert key.k is None

    def test_del_without_ssl_obj(self, mocker):
        from honeybadgerbft.crypto.ecdsa import ecdsa_ssl
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        key = KEY()
        mocker.patch.object(ecdsa_ssl, 'ssl', new=None)
        key.__del__()
	assert key.k is None

    def test_sign_and_verify(self, ec_secret):
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        key = KEY()
        key.generate(ec_secret.decode('hex'))
        key.set_compressed(True)
        key.get_privkey ().encode('hex')
        key.get_pubkey().encode('hex')
        key.get_secret().encode('hex')
        message = 'The sun is rising!'
        signature = key.sign(message)
        assert signature
        assert key.verify(message, signature)

    @mark.parametrize('compress,form', (
        (True, 'POINT_CONVERSION_COMPRESSED'),
        (False, 'POINT_CONVERSION_UNCOMPRESSED'),
    ))
    def test_set_compressed(self, compress, form, mocker):
        from honeybadgerbft.crypto.ecdsa import ecdsa_ssl
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        mocked_ssl = mocker.patch.object(ecdsa_ssl, 'ssl')
        key = KEY()
        key.set_compressed(compress)
        mocked_ssl.EC_KEY_set_conv_form.assert_called_once_with(
                                                    key.k, getattr(key, form))

    def test_set_pubkey(self, pubkey_bytes):
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        key = KEY()
        key.set_pubkey(pubkey_bytes)
        assert key.get_pubkey() == pubkey_bytes

    def test_set_privkey(self, privkey_bytes):
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        key = KEY()
        key.set_privkey(privkey_bytes)
        assert key.get_privkey() == privkey_bytes

    def test_generate(self, ec_secret, ec_private):
        from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import KEY
        k = KEY()
        k.generate(ec_secret.decode('hex'))
        k.set_compressed(True)
        privkey = k.get_privkey ().encode('hex')
        pubkey = k.get_pubkey().encode('hex')
        secret = k.get_secret().encode('hex')


def test_check_result_raises():
    from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import check_result
    with raises(ValueError):
        check_result(0, None, None)


def test_main():
    from honeybadgerbft.crypto.ecdsa.ecdsa_ssl import main
    main()
