from boldyreva import serialize, deserialize1, deserialize2
import gipc
import random

if '_procs' in globals():
    for p,pipe in _procs:
        p.terminate()
        p.join()
    del _procs
_procs = []


def _worker(PK, pipe):
    (h, sigs) = pipe.get()
    sigs = dict(sigs)
    for s in sigs:
        sigs[s] = deserialize1(sigs[s])
    h = deserialize1(h)
    sig = PK.combine_shares(sigs)
    res = PK.verify_signature(sig, h)
    pipe.put((res, serialize(sig)))


def worker_loop(PK, pipe):
    """ """
    while True:
        _worker(PK, pipe)


myPK = None

def initialize(PK, size=1):
    """ """
    global _procs, myPK
    myPK = PK
    _procs = []
    for s in range(size):
        (r,w) = gipc.pipe(duplex=True)
        p = gipc.start_process(worker_loop, args=(PK, r,))
        _procs.append((p,w))

def combine_and_verify(h, sigs):
    """ """
    # return True  # we are skipping the verification
    assert len(sigs) == myPK.k
    sigs = dict((s,serialize(v)) for s,v in sigs.iteritems())
    h = serialize(h)
    # Pick a random process
    gipc_process, pipe = _procs[random.choice(range(len(_procs)))] #random.choice(_procs)
    pipe.put((h,sigs))
    (r,s) = pipe.get()
    assert r == True
    return s, gipc_process
