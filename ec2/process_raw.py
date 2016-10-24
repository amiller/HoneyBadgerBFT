############# Process the latency from a raw screen log
import scanf
import math
import numpy
from collections import defaultdict

def process(s, txpp, N=-1, t=-1):
    endtime = dict()
    starttime = dict()
    tList = []
    lines = s.split('\n')
    scheduleTime = defaultdict(lambda: 0)
    for line in lines:
        if 'timestampE ' in line:
            info = eval(line.split('timestampE')[1])
            endtime[info[0]] = info[1]
        if 'timestampB ' in line:
            info = eval(line.split('timestampB')[1])
            starttime[info[0]] = info[1]
        if 'waits for' in line:
            if 'now is' in line:
                tl = scanf.sscanf(line, '%s out: %d waits for %f now is %f')
            else:
                tl = scanf.sscanf(line, '%s out: %d waits for %f')
            scheduleTime[tl[2]] += 1
        if 'proposing' in line:
            tl = scanf.sscanf(line, '%s out: [%d] proposing %d transactions')
            if txpp!=tl[2]:
                print "\n\n!!!!!!!!!!!!! File Inconsistent\n\n"
                return

    earlyStart = min(scheduleTime.keys())
    if scheduleTime[earlyStart] < N - t:
        print "\n\n!!!!!!!!!!!!! Starting Time Unsynced\n\n"
        return

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
    print 'N', N, 't', t
    if len(endtime) < N - t:
        print "!!!!!!!!!!!!! Census Unfinished"
        return
    print '(N-t) finishing at', sorted(endtime.values())[N-t-1] - min(starttime.values())
    print '(N/2) finishing at', sorted(endtime.values())[N/2] - min(starttime.values())
    print 'max', maxLatency
    print 'avg', sum(tList) / len(tList)
    print 'range', max(endtime.values()) - min(starttime.values())
    return sorted(endtime.values())[N-t-1] - min(starttime.values())

def processIncTx(s, txpp, N=-1, t=-1):
    endtime = dict()
    starttime = dict()
    tList = []
    lines = s.split('\n')
    scheduleTime = dict()
    for line in lines:
        if 'timestampIE ' in line:
            info = eval(line.split('timestampIE')[1])
            endtime[info[0]] = info[1]
        if 'timestampIB ' in line:
            info = eval(line.split('timestampIB')[1])
            starttime[info[0]] = info[1]
        if 'waits for' in line:
            if 'now is' in line:
                tl = scanf.sscanf(line, '%s out: %d waits for %f now is %f')
            else:
                tl = scanf.sscanf(line, '%s out: %d waits for %f')
            scheduleTime[tl[1]] = tl[2]
        if 'proposing' in line:
            tl = scanf.sscanf(line, '%s out: [%d] proposing %d transactions')
            if txpp!=tl[2]:
                print "\n\n!!!!!!!!!!!!! File Inconsistent\n\n"
                return

    uniqueScheduleTime = set(scheduleTime.values())
    print uniqueScheduleTime
    if len(uniqueScheduleTime) != 1:
        print "\n\n!!!!!!!!!!!!! Starting Time Unsynced\n\n"
        return

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
    print 'N', N, 't', t
    if len(endtime) < N - t:
        print "!!!!!!!!!!!!! Census Unfinished"
        return
    print '(N-t) finishing at', sorted(endtime.values())[N-t-1] - min(starttime.values())
    print '(N/2) finishing at', sorted(endtime.values())[N/2] - min(starttime.values())
    print 'max', maxLatency
    print 'avg', sum(tList) / len(tList)
    print 'range', max(endtime.values()) - min(starttime.values())
    return sorted(endtime.values())[N-t-1] - min(starttime.values())

def p(N, t, b):
    fileName = "logs/%d_%d_%d.txt" % (N, t, b)
    contents = open(fileName).read().strip().split('\n\n')
    re = []
    for c in contents:
        if c:
            ttt = process(c, b, N, t)
            if ttt:
                re.append(ttt)
    print tuple(re)
    print sum(re) / len(re), numpy.std(re), 'num', len(re)

def pIncTx(N, t, b):
    fileName = "logs/%d_%d_%d.txt" % (N, t, b)
    contents = open(fileName).read().strip().split('\n\n')
    re = []
    for c in contents:
        if c:
            ttt = processIncTx(c, b, N, t)
            if ttt:
                re.append(ttt)
    print sum(re) / len(re), numpy.std(re)

if  __name__ =='__main__':
  try: __IPYTHON__
  except NameError:

    import IPython
    IPython.embed()

