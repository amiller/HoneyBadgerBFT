from boldyreva import dealer, serialize, deserialize1, deserialize2
import multiprocessing 

_pool_PK = None
_pool = None

def initialize(PK):
    from multiprocessing import Pool
    global _pool
    _pool = Pool()
    print 'Pool started'

    global _pool_PK
    _pool_PK = PK

def _combine_and_verify(h, sigs):
    global _pool_PK
    sigs = dict(sigs)
    for s in sigs: 
        sigs[s] = deserialize1(sigs[s])
    h = deserialize1(h)
    sig = PK.combine_shares(sigs)
    print PK.verify_signature(sig, h)
    return True

def combine_and_verify(h, sigs):
    assert len(sigs) == _pool_PK.k
    sigs = dict((s,serialize(v)) for s,v in sigs.iteritems())
    h = serialize(h)
    promise = _pool.apply_async(_combine_and_verify, (h, sigs))
    assert promise.get() == True



def pool_test():
    global PK, SKs
    PK, SKs = dealer(players=64,k=17)

    global sigs,h
    sigs = {}
    h = PK.hash_message('hi')
    h.initPP()
    for SK in SKs:
        sigs[SK.i] = SK.sign(h)


    from multiprocessing import Pool
    pool = Pool()
    print 'Pool started'
    import time
    sigs2 = dict((s,serialize(sigs[s])) for s in range(PK.k))
    _h = serialize(h)

    # Combine 100 times
    if 1:
        promises = [pool.apply_async(_combine_and_verify, 
                                     (_h, sigs2))
                    for i in range(100)]
        print 'launched', time.time()
        for p in promises: assert p.get() == True
        print 'done', time.time()

    # Combine 100 times
    if 1:
        print 'launched', time.time()
        for i in range(100):
            _combine_and_verify(_h, sigs2)
        print 'done', time.time()

    print 'work done'
    pool.terminate()
    pool.join()
    print 'ok'
