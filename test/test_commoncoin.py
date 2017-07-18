import unittest
import gevent
import random
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.util.router import broadcast_router

### Test
def _test_commoncoin(N=4, f=1, seed=None):
    # Generate keys
    PK, SKs = dealer(N, f+1)
    sid = 'sidA'
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = broadcast_router(N, seed=seed)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]

    for i in range(10):
        threads = [gevent.spawn(c, i) for c in coins]
        gevent.joinall(threads)
        assert len(set([t.value for t in threads])) == 1
    return True

def test_commoncoin():
    _test_commoncoin()
