import matplotlib.pyplot as plt

# Measurements from the table
expt = [
    (8,2,[
        (512,5.96925),
        (1024,6.41475),
        (2048,6.402),
        (4096,7.75725),
        (8192,10.99675),
        (16384,18.7975),
        (32768,36.5285),
        (65536,70.299),
        (131072, 138.395),
        (262144, 295.122)
    ]),
    (16,4,[
        (512, 5.6815),
        (1024, 6.40175),
        (2048, 8.33675),
        (4096, 12.37275),
        (8192, 20.29125),
        (16384, 39.1535),
        (32768, 73.4515),
        (65536, 140.214)
    ]),
    (32,8,[
        (512, 9.489),
        (1024, 11.5725),
        (2048, 15.89175),
        (4096, 24.24975),
        (8192, 43.201),
        (16384, 79.7425),
        (32768, 153.85975)
    ]),
    (64, 16,[
        (512, 24.3315),
        (1024, 32.17575),
        (2048, 39.399625),
        (4096, 58.59675),
        (8192, 96.832),
        (16384, 173.94425)
    ]),
    (64, 21, [
        (512, 26.027),
        (1024, 31.5315),
        (2048, 42.291),
        (4096, 63.3355),
        (8192, 105.0055),
        (16384, 190.3235)
    ]),
    (128, 32, [
        (256, 89.2895),
        (512, 94.507),
        (1024, 105.0365),
        (2048, 122.69),
        (4096, 162.205),
        (8192, 241.219),
        (16384, 414.118)
    ])]

import os

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
    print 'N', N, 't', t
    if len(endtime) < N - t:
        print "!!!!!!!!!!!!! Consensus Unfinished"
        return None
    return sorted(endtime.values())[N-t-1] - min(starttime.values())
    
from collections import defaultdict
def getPointsFromLog(d):
    resX = defaultdict(lambda: [])
    resY = defaultdict(lambda: [])
    for file in os.listdir(d):
        if file[-4:] == '.log':
            print 'processing', file
            N = int(file[:-4].split('_')[0])
            t = int(file[:-4].split('_')[1])
            Tx = int(file[:-4].split('_')[2])
            content = open(d+'/'+file).read().split('servers')[1:]
            for s in content:
                latency = process(s)
                if latency:
                    resX[(N, t)].append(Tx * N)
                    resY[(N, t)].append(latency)
    return resX, resY

import matplotlib.cm as cm
import numpy as np

def do_plot():
    f = plt.figure(1, figsize=(7,5));
    plt.clf()
    ax = f.add_subplot(1, 1, 1)
    resX, resY = getPointsFromLog('ec2/timing')
    colors = cm.get_cmap('terrain')(np.linspace(0, 0.3, len(resX)))
    colorCounter = 0  # we cannot use *next*, bucase nparray is not iteratable
    for N, t, entries in expt:
        throughput = []
        batch = []
        for ToverN, latency in entries:
            batch.append(ToverN * N)
            throughput.append(latency)
        ax.plot(batch, throughput, label='%d/%d' % (N,t))
        ax.scatter(resX[(N, t)], resY[(N, t)], 
            label='%d/%d' % (N,t), alpha=0.5, s=1.5, color=colors[colorCounter])
        colorCounter += 1

    ax.set_xscale("log")
    ax.set_yscale("log")
    plt.ylim([10**0.2, 10**2.6])
    plt.xlim([10**2.2, 10**6.3])
    plt.legend(title='Nodes / Tolerance', loc='best')
    plt.ylabel('Latency')
    plt.xlabel('Requests (Tx)')
    plt.tight_layout()
    # plt.show()
    plt.savefig('plot_latency.pdf', format='pdf', dpi=1000)

do_plot()
