from collections import namedtuple
from enum import Enum

import gevent
from gevent.event import Event
from gevent.queue import Queue

from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.core.binaryagreement import binaryagreement
from honeybadgerbft.core.reliablebroadcast import reliablebroadcast
from honeybadgerbft.core.commonsubset import commonsubset
from honeybadgerbft.core.honeybadger_block import honeybadger_block
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.exceptions import UnknownTagError


class BroadcastTag(Enum):
    ACS_COIN = 'ACS_COIN'
    ACS_RBC = 'ACS_RBC'
    ACS_ABA = 'ACS_ABA'
    TPKE = 'TPKE'


BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', ('ACS_COIN', 'ACS_ABA', 'ACS_RBC', 'TPKE'))


def broadcast_receiver(recv_func, recv_queues):
    sender, (tag, j, msg) = recv_func()
    if tag not in BroadcastTag.__members__:
        # TODO Post python 3 port: Add exception chaining.
        # See https://www.python.org/dev/peps/pep-3134/
        raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
            tag, BroadcastTag.__members__.keys()))
    recv_queue = recv_queues._asdict()[tag]

    if tag != BroadcastTag.TPKE.value:
        recv_queue = recv_queue[j]

    recv_queue.put_nowait((sender, msg))


def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        broadcast_receiver(recv_func, recv_queues)


class HoneyBadgerBFT():
    """HoneyBadgerBFT object used to run the protocol.

    :param str sid: The base name of the common coin that will be used to
        derive a nonce to uniquely identify the coin.
    :param int pid: Node id.
    :param int B: Batch size of transactions.
    :param int N: Number of nodes in the network.
    :param int f: Number of faulty nodes that can be tolerated.
    :param str sPK: Public key of the threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param str sSK: Signing key of the threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param str ePK: Public key of the threshold encryption
        (:math:`\mathsf{TPKE}`) scheme.
    :param str eSK: Signing key of the threshold encryption
        (:math:`\mathsf{TPKE}`) scheme.
    :param send:
    :param recv:
    """

    def __init__(self, sid, pid, B, N, f, sPK, sSK, ePK, eSK, send, recv):
        self.sid = sid
        self.pid = pid
        self.B = B
        self.N = N
        self.f = f
        self.sPK = sPK
        self.sSK = sSK
        self.ePK = ePK
        self.eSK = eSK
        self._send = send
        self._recv = recv

        self.round = 0  # Current block number
        self.transaction_buffer = []
        self._per_round_recv = {}  # Buffer of incoming messages

    def submit_tx(self, tx):
        """Appends the given transaction to the transaction buffer.

        :param tx: Transaction to append to the buffer.
        """
        print 'submit_tx', self.pid, tx
        self.transaction_buffer.append(tx)

    def run(self):
        """Run the HoneyBadgerBFT protocol."""

        def _recv():
            """Receive messages."""
            while True:
                (sender, (r, msg)) = self._recv()

                # Maintain an *unbounded* recv queue for each epoch
                if r not in self._per_round_recv:
                    # Buffer this message
                    assert r >= self.round      # pragma: no cover
                    self._per_round_recv[r] = Queue()

                _recv = self._per_round_recv[r]
                if _recv is not None:
                    # Queue it
                    _recv.put((sender, msg))

                # else:
                # We have already closed this
                # round and will stop participating!

        self._recv_thread = gevent.spawn(_recv)

        while True:
            # For each round...
            r = self.round
            if r not in self._per_round_recv:
                self._per_round_recv[r] = Queue()

            # Select all the transactions (TODO: actual random selection)
            tx_to_send = self.transaction_buffer[:self.B]

            # TODO: Wait a bit if transaction buffer is not full

            # Run the round
            def _make_send(r):
                def _send(j, o):
                    self._send(j, (r, o))
                return _send
            send_r = _make_send(r)
            recv_r = self._per_round_recv[r].get
            new_tx = self._run_round(r, tx_to_send[0], send_r, recv_r)
            print 'new_tx:', new_tx

            # Remove all of the new transactions from the buffer
            self.transaction_buffer = [_tx for _tx in self.transaction_buffer if _tx not in new_tx]

            self.round += 1     # Increment the round
            if self.round >= 3: break   # Only run one round for now

    def _run_round(self, r, tx_to_send, send, recv):
        """Run one protocol round.

        :param int r: round id
        :param tx_to_send: Transaction(s) to process.
        :param send:
        :param recv:
        """
        # Unique sid for each round
        sid = self.sid + ':' + str(r)
        pid = self.pid
        N = self.N
        f = self.f

        def broadcast(o):
            """Multicast the given input ``o``.

            :param o: Input to multicast.
            """
            for j in range(N): send(j, o)

        # Launch ACS, ABA, instances
        coin_recvs = [None] * N
        aba_recvs = [None] * N
        rbc_recvs = [None] * N

        aba_inputs = [Queue(1) for _ in range(N)]
        aba_outputs = [Queue(1) for _ in range(N)]
        rbc_outputs = [Queue(1) for _ in range(N)]

        my_rbc_input = Queue(1)
        print pid, r, 'tx_to_send:', tx_to_send

        def _setup(j):
            """Setup the sub protocols RBC, BA and common coin.

            :param int j: Node index for which the setup is being done.
            """
            def coin_bcast(o):
                """Common coin multicast operation.

                :param o: Value to multicast.
                """
                broadcast(('ACS_COIN', j, o))

            coin_recvs[j] = Queue()
            coin = shared_coin(sid + 'COIN' + str(j), pid, N, f,
                               self.sPK, self.sSK,
                               coin_bcast, coin_recvs[j].get)

            def aba_bcast(o):
                """Binary Byzantine Agreement multicast operation.

                :param o: Value to multicast.
                """
                broadcast(('ACS_ABA', j, o))

            aba_recvs[j] = Queue()
            aba = gevent.spawn(binaryagreement, sid+'ABA'+str(j), pid, N, f, coin,
                               aba_inputs[j].get, aba_outputs[j].put_nowait,
                               aba_bcast, aba_recvs[j].get)

            def rbc_send(k, o):
                """Reliable broadcast operation.

                :param o: Value to broadcast.
                """
                send(k, ('ACS_RBC', j, o))

            # Only leader gets input
            rbc_input = my_rbc_input.get if j == pid else None
            rbc_recvs[j] = Queue()
            rbc = gevent.spawn(reliablebroadcast, sid+'RBC'+str(j), pid, N, f, j,
                               rbc_input, rbc_recvs[j].get, rbc_send)
            rbc_outputs[j] = rbc.get  # block for output from rbc

        # N instances of ABA, RBC
        for j in range(N): _setup(j)

        # One instance of TPKE
        def tpke_bcast(o):
            """Threshold encryption broadcast."""
            broadcast(('TPKE', 0, o))

        tpke_recv = Queue()

        # One instance of ACS
        acs = gevent.spawn(commonsubset, pid, N, f, rbc_outputs,
                           [_.put_nowait for _ in aba_inputs],
                           [_.get for _ in aba_outputs])

        recv_queues = BroadcastReceiverQueues(
            ACS_COIN=coin_recvs,
            ACS_ABA=aba_recvs,
            ACS_RBC=rbc_recvs,
            TPKE=tpke_recv,
        )
        gevent.spawn(broadcast_receiver_loop, recv, recv_queues)

        _input = Queue(1)
        _input.put(tx_to_send)
        return honeybadger_block(pid, self.N, self.f, self.ePK, self. eSK,
                                 _input.get,
                                 acs_in=my_rbc_input.put_nowait, acs_out=acs.get,
                                 tpke_bcast=tpke_bcast, tpke_recv=tpke_recv.get)
