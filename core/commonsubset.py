import gevent

def commonsubset(sid, pid, N, f, rbc_out, aba_in, aba_out):
    """The BKR93 algorithm for asynchronous common subset.
    :param sid: session string
    :param pid: my identifier
    :param N: number of nodes
    :param f: fault tolerance
    :param input: input() is called to block and wait for input
    :param rbc_in: a single input function rbc_in(v) provides input
    :param rbc_out: an array of N input functions
    :param abas: an array of N twoples, [(in,out), ...]

    :return: an N-element array, each element either None or a string
    """
    assert len(rbc_out) == N
    assert len(aba_in ) == N
    assert len(aba_out) == N

    aba_inputted = [False] * N
    aba_values = [0] * N
    rbc_values = [None] * N

    def _recv_rbc(j):
        # Receive output from reliable broadcast
        rbc_values[j] = rbc_out[j]()

        if not aba_inputted[j]:
            # Provide 1 as input to the corresponding bin agreement
            aba_inputted[j] = True
            aba_in[j]( 1 )

    r_threads = [gevent.spawn(_recv_rbc, j) for j in range(N)]
        
    def _recv_aba(j):
        # Receive output from binary agreement
        aba_values[j] = aba_out[j]()
        if sum(aba_values) >= N - f:
            # Provide 0 to all other aba
            for k in range(N):
                if not aba_inputted[k]:
                    aba_inputted[k] = True
                    aba_in[k]( 0 )

    # Wait for all binary agreements
    a_threads = [gevent.spawn(_recv_aba, j) for j in range(N)]
    gevent.joinall(a_threads)

    assert sum(aba_values) >= N - f  # Must have at least N-f committed

    # Wait for the corresponding broadcasts
    for j in range(N):
        if aba_values[j]:
            r_threads[j].join()
            assert rbc_values[j] is not None
        else:
            r_threads[j].kill()
            rbc_values[j] = None

    return tuple(rbc_values)
