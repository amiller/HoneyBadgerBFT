################################

import sys
import re

infoExtractor = re.compile(r'(?P<index>\d+):(?P<bytes>\d+)\((?P<from>\d+)\-\>(?P<to>\d+)\)\[(?P<start_time>[\d\.]+)\]-\[(?P<end_time>[\d\.]+)\]\((?P<sender>\d+),\s*(?P<content>.*)\)')

def main(filename):
    # Generate summaries and chart.
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
    # return

    import matplotlib.pyplot as plt

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
    plt.plot(xs, density(xs))
    plt.show()

if __name__=='__main__':
    main(sys.argv[1])
