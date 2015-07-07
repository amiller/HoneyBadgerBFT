import gevent



def forkThread():
    return 1

def bv_broadcast(sid, multicast, receive):
    pid, ssid = sid

    def input(v):
        multicast(("BC",v))

        forkThread
