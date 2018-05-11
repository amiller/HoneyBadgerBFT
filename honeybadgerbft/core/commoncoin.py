from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1
from collections import defaultdict
from gevent import Greenlet
from gevent.queue import Queue
import hashlib


class CommonCoinFailureException(Exception):
    """Raised for common coin failures."""
    pass


hash = lambda x: hashlib.sha256(x).digest()


def shared_coin(sid, pid, N, f, PK, SK, broadcast, receive):
    """A shared coin based on threshold signatures

    :param sid: a unique instance id
    :param pid: my id number
    :param N: number of parties
    :param f: fault tolerance, :math:`f+1` shares needed to get the coin
    :param PK: ``boldyreva.TBLSPublicKey``
    :param SK: ``boldyreva.TBLSPrivateKey``
    :param broadcast: broadcast channel
    :param receive: receive channel
    :return: a function ``getCoin()``, where ``getCoin(r)`` blocks
    """
    assert PK.k == f+1
    assert PK.l == N
    received = defaultdict(dict)
    outputQueue = defaultdict(lambda: Queue(1))

    def _recv():
        while True: # main receive loop
            # New shares for some round r, from sender i
            (i, (_, r, sig)) = receive()
            assert i in range(N)
            assert r >= 0
            if i in received[r]:
                print "redundant coin sig received", (sid, pid, i, r)
                continue

            h = PK.hash_message(str((sid, r)))

            # TODO: Accountability: Optimistically skip verifying
            # each share, knowing evidence available later
            try: PK.verify_share(sig, i, h)
            except AssertionError:
                print "Signature share failed!", (sid, pid, i, r)
                continue

            received[r][i] = sig

            # After reaching the threshold, compute the output and
            # make it available locally
            if len(received[r]) == f + 1:

                # Verify and get the combined signature
                sigs = dict(list(received[r].iteritems())[:f+1])
                sig = PK.combine_shares(sigs)
                assert PK.verify_signature(sig, h)

                # Compute the bit from the least bit of the hash
                bit = ord(hash(serialize(sig))[0]) % 2
                outputQueue[r].put_nowait(bit)

    # greenletPacker(Greenlet(_recv), 'shared_coin', (pid, N, f, broadcast, receive)).start()
    Greenlet(_recv).start()

    def getCoin(round):
        """Gets a coin.

        :param round: the epoch/round.
        :returns: a coin.

        """
        # I have to do mapping to 1..l
        h = PK.hash_message(str((sid, round)))
        broadcast(('COIN', round, SK.sign(h)))
        return outputQueue[round].get()

    return getCoin
