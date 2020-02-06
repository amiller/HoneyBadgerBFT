# Basically care about two timestamps
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import re
import glob
import numpy as np

import scipy.stats as st
def conf(c=0.95, a=[]):
    return st.t.interval(c, len(a)-1, loc=np.mean(a), scale=st.sem(a))

# Special case for N=128, run from last time 
special = (128, '-^', [
        (256, 89.2895),
        (512, 94.507),
        (1024, 105.0365),
        (2048, 122.69),
        (4096, 162.205),
        (8192, 241.219)])

expt = {
    # 8: ('-o', [1024,2048,4096,8192,16384,32768,65536,131072]),
    #16: ('--+', [512,1024,2048,4096,8192,16384,32768,65536]),
    32: ('-*', [512,1024,2048,4096,8192,16384,32768]),
    40: ('--o', [1024,2048,4096,8192,16384,32768]),
    48: ('-d', [1024,2048,4096,8192,16384,32768]),
    56: ('--^', [1024,2048,4096,8192,16384,32768]),
    64: ('--+', [1024,2048,4096,8192,16384,32768]),
    104: ('-o', [512,1024,2048,4096,8192]),
    }

def read_all():
    for N in [8]:
        for B in [1024,2048,4096,8192,16384,32768,65536,131072]:
            print read_samples(N,B)

def read_samples(N,B):
    files = sorted(glob.glob('logs/ec2log_%d_%d_*.log' % (N,B)))
    vals = []
    comms = []
    for f in files:
        stops, comm = readfile(N, open(f))
        nth = sorted(stops)[N-N/4-1]
        vals.append(nth)
        comms.append(comm)
    return vals, comms

def readfile(N, f):
    start = None
    comm = None
    stops = []
    for line in f:
        m = re.search('waits for (\d+\.\d+)', line)
        if m: start, = m.groups()
        m = re.search('timestampE \(\d+, (\d+\.\d+)\)', line)
        if m: 
            stop, = m.groups()
            stops.append(float(stop) - float(start))
        m = re.search('(\d+) distinct tx synced', line)
        if m: 
            comm, = m.groups()
            comm = int(comm)
    return stops, comm

def plot_throughput():
    f = plt.figure(1, figsize=(7,5));
    plt.clf()
    ax = f.add_subplot(1, 1, 1)
    for N,(style,entries) in sorted(expt.iteritems()):
        t = N/4
        yvals = []
        yvalL = []
        yvalU = []
        batch = []
        for ToverN in entries:
            latencies,comm = read_samples(N, ToverN)
            latencies = np.array(latencies)
            if not len(latencies): continue
            throughput = comm / latencies
            batch.append(ToverN*N)
            #throughput.append(ToverN*(N-t) / latencies)
            #batch.append(ToverN*(N-t) / np.mean(latencies))
            yvals.append(np.median(throughput))
            lo,hi = conf(0.95, throughput)
            yvalL.append( np.median(throughput) - lo )
            yvalU.append( hi - np.median(throughput) )
            #yvalL.append( np.median(throughput) - np.min(throughput))
            #yvalU.append( np.max(throughput) - np.median(throughput))

        #ax.plot(batch, yvals, style, label='%d/%d' % (N,t))
        ax.errorbar(batch, yvals, yerr=[yvalL, yvalU], label='%d/%d' % (N,t), fmt=style)
    ax.set_xscale("log")
    ax.set_yscale("log")
    plt.ylim([1e2,3e4])
    plt.xlim(xmin=1.5e4,xmax=3e6)
    plt.legend(title='Nodes / Tolerance', loc='best', ncol=2)
    plt.ylabel('Throughput (Tx per second) in log scale')
    #plt.ylabel('Latency')
    #plt.xlabel('Throughput')
    plt.xlabel('Batch size (Tx) in log scale')
    plt.yticks([100, 1000, 10000])
    plt.tight_layout()
    plt.show()
    plt.savefig('plot_throughput_aug13.pdf', format='pdf', dpi=1000)

def plot_latency_throughput():
    f = plt.figure(1, figsize=(7,5));
    plt.clf()
    ax = f.add_subplot(1, 1, 1)
    for N,(style,entries) in sorted(expt.iteritems()):
        t = N/4
        yvals = []
        yvalL = []
        yvalU = []
        xvals = []
        for ToverN in entries:
            latencies,comms = read_samples(N, ToverN)
            latencies = np.array(latencies)
            if not len(latencies): continue
            throughput = comms / latencies
            xvals.append(np.median(throughput))
            yvals.append(np.median(latencies))
            lo,hi = conf(0.95, latencies)
            yvalL.append( np.median(latencies) - lo )
            yvalU.append( hi - np.median(latencies) )
            #yvalL.append( np.median(latencies) - np.min(latencies))
            #yvalU.append( np.max(latencies) - np.median(latencies))
        ax.errorbar(xvals, yvals, yerr=[yvalL, yvalU], label='%d/%d' % (N,t), fmt=style)
    # for N,style,entries in [special]:
    #     t = N/4
    #     latencies = []
    #     throughputs = []
    #     for ToverN, latency in entries:
    #         throughput = ToverN*(N-t) / latency
    #         throughputs.append(throughput)
    #         latencies.append(latency)
    #     ax.plot(throughputs, latencies, style, label='%d/%d$^*$' % (N,t))
    #ax.set_xscale("log")
    ax.set_yscale("log")
    plt.ylim([-1, 500])
    plt.xlim(xmax=21200)
    plt.legend(title='Nodes / Tolerance', loc='best', ncol=3)
    plt.ylabel('Latency (seconds) in log scale')
    plt.xlabel('Throughput (Tx per second)')
    plt.tight_layout()
    plt.show()
    plt.savefig('plot_latency_throughput_aug13.pdf', format='pdf', dpi=1000)
            

# waits for 1471088150.0
# timestampE (1, 1471088204.750964)
print "Creating plot_throughput:"
plot_throughput()
print "Done."
print "Creating plot_latency_throughput:"
plot_latency_throughput()
print "Done."
