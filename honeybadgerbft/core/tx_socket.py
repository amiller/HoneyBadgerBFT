import socket
import os

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
# of committed txes.
class TxSocket():
    def __init__(self, sock, encode, decode, max_size):
        self.socket = sock
        self.connected = False
        self.encode = encode
        self.decode = decode
        self.max_size = max_size

    def write(self, txes):
        assert self.connected # We assume we read before writing

        self.socket.send(self.encode(txes))

    def read(self):
        payload, sender = self.socket.recvfrom(self.max_size)
        if not self.connected:
            self.socket.connect(sender)
            self.connected = True

        return self.decode(payload)

def bind_codec_socket(path, encode, decode, max_size=65536):
    return TxSocket(bind_datagram_socket(path), encode, decode, max_size)
