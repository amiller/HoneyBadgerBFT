################################

import sys
import re
from datetime import datetime
import time

# sample: 5[[09-08-15|11:51:19]]-[[09-08-15|11:51:19]](0, ('BC', ('initial', 0, set([[94m{{Transaction from Alice to Eco with 26}}[0m]), '\xcf\x04\xad1\x8b\x91-\x00\xf5\xdf\xdc\xa4\xc7N\xb9\xba\xa88\x19CPPnl\x1e\xd0\xb7\x00J\x9f\xb8$u4"r\xd9\xa5\xc4\xbdc\xf4\x90\x10\x92\xb8\xd28')))
# infoExtractor = re.compile(r'(?P<index>\d+)\[\[(?P<start_time>[\d\-\|:]+)\]\]-\[\[(?P<end_time>[\d\-\|:]+)\]\]\((?P<sender>\d+),\s*(?P<content>.*)\)')
infoExtractor = re.compile(r'(?P<index>\d+):(?P<bytes>\d+)\((?P<from>\d+)\-\>(?P<to>\d+)\)\[(?P<start_time>[\d\.]+)\]-\[(?P<end_time>[\d\.]+)\]\((?P<sender>\d+),\s*(?P<content>.*)\)')
# For bitmessage and Freenet (no sender)
# infoExtractor = re.compile(r'(?P<index>\d+):(?P<bytes>\d+)\[(?P<start_time>[\d\.]+)\]-\[(?P<end_time>[\d\.]+)\]\(\s*(?P<content>.*)\)')

def main(filename):
    content = open(filename, 'r').read().decode('utf-8','ignore')
    timelap = []
    start_times = []
    end_times = []
    msgsize = []
    outputObj = []
    import json
    infoList = [a for a in infoExtractor.finditer(content)]
    if not infoList:
        return

    for mat in infoList:
        res = mat.groupdict()
        start_times.append(float(res['start_time']))
        # print start_times
        end_times.append(float(res['end_time']))
        time_diff = float(res['end_time']) - float(res['start_time'])
        timelap.append(time_diff)
        msgsize.append(int(res['bytes']))

        outputObj.append([
            res['from'], "(%s->%s)%s" % (res['from'], res['to'], res['content']), '|'+str(float(res['start_time']))+'|', '|'+str(float(res['end_time']))+'|'
            ])

    open('rawdata.'+filename,'w').write(json.dumps(outputObj).replace('"|','new Date(').replace('|"','*1000)'))
    # return
    import numpy

    print max(end_times) - min(start_times)
    print len(msgsize)
    print sum(msgsize)
    print sum(timelap) / len(timelap)
    print numpy.var(timelap)
    print max(timelap)
    return

    import matplotlib.pyplot as plt

    from numpy.random import normal
    plt.hist(timelap, bins=50)
    plt.title("Histogram")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.show()

    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import gaussian_kde
    data = timelap
    density = gaussian_kde(data)
    xs = np.linspace(0,8,200)
    density.covariance_factor = lambda : .45
    density._compute_covariance()
    plt.plot(xs,density(xs))
    plt.show()

if __name__=='__main__':
    main(sys.argv[1])
