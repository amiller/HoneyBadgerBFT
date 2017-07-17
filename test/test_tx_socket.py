import unittest
import gevent
import rlp
import socket
from honeybadgerbft.core.tx_socket import bind_rlp_socket

def _test_rlp_round_trip():
    server_path = "/tmp/rlp-test-server"
    rlp_sock = bind_rlp_socket(server_path)
    txes = ["x", "y", "z"]

    raw_client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    raw_client.bind("/tmp/rlp-test-client")
    raw_client.connect(server_path)
    raw_client.send(rlp.encode(txes))

    assert rlp_sock.read() == txes

from nose2.tools import params

def test_tx_socket():
    _test_rlp_round_trip()
