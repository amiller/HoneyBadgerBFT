import gevent
from gevent.event import Event
from collections import defaultdict

from honeybadgerbft.exceptions import RedundantMessageError


def binaryagreement(sid, pid, N, f, coin, input, decide, broadcast, receive):
    """Binary consensus from [MMR14]. It takes an input ``vi`` and will
    finally write the decided value into ``decide`` channel.

    :param sid: session identifier
    :param pid: my id number
    :param N: the number of parties
    :param f: the number of byzantine parties
    :param coin: a ``common coin(r)`` is called to block until receiving a bit
    :param input: ``input()`` is called to receive an input
    :param decide: ``decide(0)`` or ``output(1)`` is eventually called
    :param broadcast: broadcast channel
    :param receive: receive channel
    :return: blocks until
    """
    # Messages received are routed to either a shared coin, the broadcast, or AUX
    est_values = defaultdict(lambda: [set(), set()])
    aux_values = defaultdict(lambda: [set(), set()])
    est_sent = defaultdict(lambda: [False, False])
    bin_values = defaultdict(set)

    # This event is triggered whenever bin_values or aux_values changes
    bv_signal = Event()

    def _recv():
        while True:  #not finished[pid]:
            (sender, msg) = receive()
            assert sender in range(N)
            if msg[0] == 'EST':
                # BV_Broadcast message
                _, r, v = msg
                assert v in (0, 1)
                if sender in est_values[r][v]:
                    # FIXME: raise or continue? For now will raise just
                    # because it appeared first, but maybe the protocol simply
                    # needs to continue.
                    print 'Redundant EST received', msg
                    raise RedundantMessageError(
                        'Redundant EST received {}'.format(msg))
                    # continue

                est_values[r][v].add(sender)
                # Relay after reaching first threshold
                if len(est_values[r][v]) >= f + 1 and not est_sent[r][v]:
                    est_sent[r][v] = True
                    broadcast(('EST', r, v))

                # Output after reaching second threshold
                if len(est_values[r][v]) >= 2 * f + 1:
                    bin_values[r].add(v)
                    bv_signal.set()

            elif msg[0] == 'AUX':
                # Aux message
                _, r, v = msg
                assert v in (0, 1)
                if sender in aux_values[r][v]:
                    # FIXME: raise or continue? For now will raise just
                    # because it appeared first, but maybe the protocol simply
                    # needs to continue.
                    print 'Redundant AUX received', msg
                    raise RedundantMessageError(
                        'Redundant AUX received {}'.format(msg))
                    # continue

                aux_values[r][v].add(sender)
                bv_signal.set()

    # Translate mmr14 broadcast into coin.broadcast
    #_coin_broadcast = lambda (r, sig): broadcast(('COIN', r, sig))
    #_coin_recv = Queue()
    #coin = shared_coin(sid+'COIN', pid, N, f, _coin_broadcast, _coin_recv.get)

    # Run the receive loop in the background
    _thread_recv = gevent.spawn(_recv)

    # Block waiting for the input
    vi = input()
    assert vi in (0, 1)
    est = vi
    r = 0
    already_decided = None
    while True:  # Unbounded number of rounds
        if not est_sent[r][est]:
            est_sent[r][est] = True
            broadcast(('EST', r, est))

        while len(bin_values[r]) == 0:
            # Block until a value is output
            bv_signal.clear()
            bv_signal.wait()

        w = next(iter(bin_values[r]))  # take an element
        broadcast(('AUX', r, w))

        values = None
        while True:
            # Block until at least N-f AUX values are received
            if 1 in bin_values[r] and len(aux_values[r][1]) >= N - f:
                values = set((1,))
                #print '[sid:%s] [pid:%d] VALUES 1 %d' % (sid,pid,r)
                break
            if 0 in bin_values[r] and len(aux_values[r][0]) >= N - f:
                values = set((0,))
                #print '[sid:%s] [pid:%d] VALUES 0 %d' % (sid,pid,r)
                break
            if sum(len(aux_values[r][v]) for v in bin_values[r]) >= N - f:
                values = set((0, 1))
                #print '[sid:%s] [pid:%d] VALUES BOTH %d' % (sid,pid,r)
                break
            bv_signal.clear()
            bv_signal.wait()

        # Block until receiving the common coin value
        s = coin(r)

        if len(values) == 1:
            v = next(iter(values))
            if v == s:
                if already_decided is None:
                    already_decided = v
                    decide(v)
                    #print '[sid:%s] [pid:%d] DECIDED %d in round %d' % (sid,pid,v,r)
                elif already_decided == v:
                    # Here corresponds to a proof that if one party
                    # decides at round r, then in all the following
                    # rounds, everybody will propose r as an
                    # estimation. (Lemma 2, Lemma 1) An abandoned
                    # party is a party who has decided but no enough
                    # peers to help him end the loop.  Lemma: # of
                    # abandoned party <= t
                    #print '[sid:%s] [pid:%d] QUITTING in round %d' % (sid,pid,r)
                    _thread_recv.kill()
                    return
                est = v
        else:
            est = s
        r += 1
