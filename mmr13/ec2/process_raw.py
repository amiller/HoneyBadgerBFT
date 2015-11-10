############# Process the latency from a raw screen log
def process(s, N=-1, t=-1):
    endtime = dict()
    starttime = dict()
    tList = []
    lines = s.split('\n')
    for line in lines:
        if 'timestampE' in line:
            info = eval(line.split('timestampE')[1])
            endtime[info[0]] = info[1]
        if 'timestampB' in line:
            info = eval(line.split('timestampB')[1])
            starttime[info[0]] = info[1]
    maxLatency = 0
    for key, value in endtime.items():
        print key, starttime[key], value, value - starttime[key]
        tList.append(value - starttime[key])
        if value - starttime[key] > maxLatency:
            maxLatency = value - starttime[key]
    if N < 0 or t < 0 or 3*t < N:
        # infer N, t
        N = len(starttime.keys())
        t = N/4  # follows the convention that 4t = N
    print '(N-t) finishing at', sorted(endtime.values())[N-t-1] - min(starttime.values())
    print '(N/2) finishing at', sorted(endtime.values())[N/2] - min(starttime.values())
    print 'max', maxLatency
    print 'avg', sum(tList) / len(tList)
    print 'range', max(endtime.values()) - min(starttime.values())

if  __name__ =='__main__':
  try: __IPYTHON__
  except NameError:

    import IPython
    IPython.embed()

