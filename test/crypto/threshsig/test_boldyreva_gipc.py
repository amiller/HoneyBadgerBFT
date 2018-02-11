import time

import gevent
import gipc

from pytest import raises


def test_worker(tbls_public_key, tbls_private_keys):
    from honeybadgerbft.crypto.threshsig.boldyreva_gipc import _worker
    from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1
    r_pipe, w_pipe = gipc.pipe(duplex=True)
    h = tbls_public_key.hash_message('hi')
    h.initPP()
    signature_shares = {sk.i: sk.sign(h) for sk in tbls_private_keys}
    serialized_h = serialize(h)
    serialized_signature_shares = {
        k: serialize(v) for k, v in signature_shares.items()
        if k in signature_shares.keys()[:tbls_public_key.k]
    }
    w_pipe.put((serialized_h, serialized_signature_shares))
    _worker(tbls_public_key, r_pipe)
    siganture_verification_result, serialized_signature = w_pipe.get()
    assert siganture_verification_result is True
    deserialized_signature_shares = {
        k: deserialize1(v) for k, v in serialized_signature_shares.items()}
    expected_serialized_signature = serialize(
        tbls_public_key.combine_shares(deserialized_signature_shares))
    assert serialized_signature == expected_serialized_signature


def test_worker_loop(mocker, tbls_public_key):
    from honeybadgerbft.crypto.threshsig import boldyreva_gipc
    mocked_worker = mocker.patch.object(
        boldyreva_gipc, '_worker', autospec=True)
    max_calls = 3
    mocked_worker.side_effect = ErrorAfter(max_calls)
    r_pipe, _ = gipc.pipe(duplex=True)
    with raises(CallableExhausted) as err:
        boldyreva_gipc.worker_loop(tbls_public_key, r_pipe)
    mocked_worker.call_count == max_calls + 1
    mocked_worker.assert_called_with(tbls_public_key, r_pipe)


def test_pool():
    from honeybadgerbft.crypto.threshsig.boldyreva import dealer
    from honeybadgerbft.crypto.threshsig import boldyreva_gipc
    from honeybadgerbft.crypto.threshsig.boldyreva_gipc import (
            initialize, combine_and_verify)
    global PK, SKs
    PK, SKs = dealer(players=64, k=17)

    global sigs,h
    sigs = {}
    h = PK.hash_message('hi')
    h.initPP()
    for SK in SKs:
        sigs[SK.i] = SK.sign(h)

    assert not boldyreva_gipc._procs
    initialize(PK)
    assert boldyreva_gipc._procs

    sigs = dict(list(sigs.iteritems())[:PK.k])

    # Combine 100 times
    if 1:
        #promises = [pool.apply_async(_combine_and_verify,
        #                             (_h, sigs2))
        #            for i in range(100)]
        threads = []
        for i in range(3):
            threads.append(gevent.spawn(combine_and_verify, h, sigs))
        print 'launched', time.time()
        greenlets = gevent.joinall(threads, timeout=3)
        #for p in promises: assert p.get() == True
        for greenlet in greenlets:
            assert greenlet.value[0]    # TODO check the value
            process = greenlet.value[1]
            process.terminate()
            process.join()
        print 'done', time.time()

    # Combine 100 times
    if 0:
        print 'launched', time.time()
        for i in range(10):
            # XXX Since _combine_and_verify is not defined, use
            # combine_and_verify instead, although not sure if that was the
            # initial intention.
            #_combine_and_verify(_h, sigs2)
            combine_and_verify(_h, sigs2)
        print 'done', time.time()

    print 'work done'
    assert boldyreva_gipc._procs
    reload(boldyreva_gipc)
    assert not boldyreva_gipc._procs


class ErrorAfter(object):
    """Callable that will raise ``CallableExhausted``
    exception after ``limit`` calls.

    credit: Igor Sobreira
        http://igorsobreira.com/2013/03/17/testing-infinite-loops.html
    """
    def __init__(self, limit):
        self.limit = limit
        self.calls = 0

    def __call__(self, x, y):
        self.calls += 1
        if self.calls > self.limit:
            raise CallableExhausted


class CallableExhausted(Exception):
    pass
