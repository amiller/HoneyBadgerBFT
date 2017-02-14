from boldyreva import dealer, serialize, deserialize1, deserialize2
import gevent
import gipc
import time
import random

if '_procs' in globals():
    for p,pipe in _procs: 
        p.terminate()
        p.join()
    del _procs
_procs = []

def _worker(PK,pipe):
    while True:
        (h, sigs) = pipe.get()
        sigs = dict(sigs)
        for s in sigs: 
            sigs[s] = deserialize1(sigs[s])
        h = deserialize1(h)
        sig = PK.combine_shares(sigs)
        res = PK.verify_signature(sig, h)
        pipe.put((res,serialize(sig)))

myPK = None

def initialize(PK, size=1):
    global _procs, myPK
    myPK = PK
    _procs = []
    for s in range(size):
        (r,w) = gipc.pipe(duplex=True)
        p = gipc.start_process(_worker, args=(PK, r,))
        _procs.append((p,w))

def combine_and_verify(h, sigs):
    # return True  # we are skipping the verification
    assert len(sigs) == myPK.k
    sigs = dict((s,serialize(v)) for s,v in sigs.iteritems())
    h = serialize(h)
    # Pick a random process
    _,pipe = _procs[random.choice(range(len(_procs)))] #random.choice(_procs)
    pipe.put((h,sigs))
    (r,s) = pipe.get() 
    assert r == True
    return s

def pool_test():
    global PK, SKs
    PK, SKs = dealer(players=64,k=17)

    global sigs,h
    sigs = {}
    h = PK.hash_message('hi')
    h.initPP()
    for SK in SKs:
        sigs[SK.i] = SK.sign(h)

    initialize(PK)

    sigs = dict(list(sigs.iteritems())[:PK.k])

    # Combine 100 times
    if 1:
        #promises = [pool.apply_async(_combine_and_verify, 
        #                             (_h, sigs2))
        #            for i in range(100)]
        threads = []
        for i in range(100):
            threads.append(gevent.spawn(combine_and_verify, h, sigs))
        print 'launched', time.time()
        gevent.joinall(threads)
        #for p in promises: assert p.get() == True
        print 'done', time.time()

    # Combine 100 times
    if 0:
        print 'launched', time.time()
        for i in range(10):
            _combine_and_verify(_h, sigs2)
        print 'done', time.time()

    print 'work done'
