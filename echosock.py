import socket
import os

ECHO_SOCK = "/tmp/hb"
GETH_SOCK = "/tmp/gethsock"

if __name__ == "__main__":
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    try:
        sock.bind(ECHO_SOCK)
        
        while True:
            recv_payload, client_addr = sock.recvfrom(10000000)
            print "echoing txes"
            sock.sendto(recv_payload, GETH_SOCK)
    finally:
        sock.close()
        sock = None
        os.remove(ECHO_SOCK)
