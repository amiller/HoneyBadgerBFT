import socket
import os
import ast
import rlp
from ethereum.transactions import Transaction # for RLP encode/decode

def bind_datagram_socket(path):
    # Make sure the socket doesn't already exist:
    try:
        os.unlink(path)
    except OSError:
        if os.path.exists(path):
            raise

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)

    return sock

# Assumes that we read input txes from the client before writing a response
# (post-consensus).
class TxSocket():
    def __init__(self, sock, serialize, deserialize, max_size):
        self.socket = sock
        self.connected = False
        self.serialize = serialize
        self.deserialize = deserialize
        self.max_size = max_size

    def write(self, txes):
        assert self.connected # We assume we read before writing

        self.socket.send(self.serialize(txes))

    def read(self):
        payload, sender = self.socket.recvfrom(self.max_size)
        if not self.connected:
            self.socket.connect(sender)
            self.connected = True

        return self.deserialize(payload)

def bind_repr_socket(path, max_size=4096):
    return TxSocket(bind_datagram_socket(path), repr, ast.literal_eval, max_size)

def bind_rlp_socket(path, max_size=65536):
    return TxSocket(bind_datagram_socket(path), rlp.encode, rlp.decode, max_size)
