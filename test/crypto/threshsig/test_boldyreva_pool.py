from multiprocessing.pool import Pool


def test_initialize(tbls_public_key):
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import (
                                                initialize, _pool, _pool_PK)
    assert _pool is None
    assert _pool_PK is None
    initialize(tbls_public_key)
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import _pool, _pool_PK
    assert isinstance(_pool, Pool)
    assert _pool_PK == tbls_public_key
    _pool.terminate()


def test_combine_and_verify(tbls_public_key, tbls_private_keys):
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import (
                                            initialize, combine_and_verify)
    h = tbls_public_key.hash_message('hi')
    h.initPP()
    signature_shares = {sk.i: sk.sign(h) for sk in tbls_private_keys}
    signature_shares = {
        k: v for k, v in signature_shares.items()
        if k in signature_shares.keys()[:tbls_public_key.k]
    }
    initialize(tbls_public_key)
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import _pool
    combine_and_verify(h, signature_shares)
    _pool.terminate()


def test__combine_and_verify(tbls_public_key, tbls_private_keys):
    from honeybadgerbft.crypto.threshsig.boldyreva import serialize
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import _combine_and_verify
    h = tbls_public_key.hash_message('hi')
    h.initPP()
    serialized_h = serialize(h)
    signature_shares = {sk.i: sk.sign(h) for sk in tbls_private_keys}
    serialized_signature_shares = {
        k: serialize(v) for k, v in signature_shares.items()
        if k in signature_shares.keys()[:tbls_public_key.k]
    }
    _combine_and_verify(
        serialized_h, serialized_signature_shares, pk=tbls_public_key)


def test_pool():
    from honeybadgerbft.crypto.threshsig.boldyreva_pool import pool_test
    pool_test()
