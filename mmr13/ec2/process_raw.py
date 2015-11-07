############# Process the latency from a raw screen log
def process(s):
    endtime = dict()
    starttime = dict()
    t = []
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
        t.append(value - starttime[key])
        if value - starttime[key] > maxLatency:
            maxLatency = value - starttime[key]
    print 'max', maxLatency
    print 'avg', sum(t) / len(t)
    print 'range', max(endtime.values()) - min(starttime.values())

if  __name__ =='__main__':
  try: __IPYTHON__
  except NameError:

    import IPython
    IPython.embed()

