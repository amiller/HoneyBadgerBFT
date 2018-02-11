from pytest import mark, raises


@mark.parametrize('n', (-1, 0, 1))
def test_is_probable_prime_raises(n):
    from honeybadgerbft.crypto.threshsig.millerrabin import is_probable_prime
    with raises(AssertionError):
        is_probable_prime(n)


@mark.parametrize('n,is_prime', (
    (2, True),
    (3, True),
    (4, False),
    (5, True),
    (123456789, False),
    (int('64380800680355443923012985496149269915138610753401343'
         '29180734395241382648423706300613697153947391340909229'
         '37332590384720397133335969549256322620979036686633213'
         '903952966175107096769180017646161851573147596390153'), True),
    (int('74380800680355443923012985496149269915138610753401343'
         '29180734395241382648423706300613697153947391340909229'
         '37332590384720397133335969549256322620979036686633213'
         '903952966175107096769180017646161851573147596390153'), False),
))
def test_is_probable_prime(n, is_prime):
    from honeybadgerbft.crypto.threshsig.millerrabin import is_probable_prime
    assert is_probable_prime(n) is is_prime


def test_is_probable_prime_under_1000():
    from honeybadgerbft.crypto.threshsig.millerrabin import is_probable_prime
    primes_under_1000 = [i for i in range(2, 1000) if is_probable_prime(i)]
    assert len(primes_under_1000) == 168
    assert primes_under_1000[-10:] == [937, 941, 947, 953, 967,
                                       971, 977, 983, 991, 997]


@mark.parametrize('bit_length', range(12, 120, 12))
def test_generate_large_prime(bit_length):
    from honeybadgerbft.crypto.threshsig.millerrabin import generateLargePrime
    assert generateLargePrime(bit_length)


def test_generate_large_prime_fails(monkeypatch):
    from honeybadgerbft.crypto.threshsig import millerrabin
    monkeypatch.setattr(millerrabin, 'is_probable_prime', lambda k: False)
    assert millerrabin.generateLargePrime(1) == 'Failure after 100.0 tries.'
