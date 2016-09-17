################################

import sys
import re

infoExtractor = re.compile(r'(?P<index>\d+):(?P<bytes>\d+)\[(?P<start_time>[\d\.]+)\]-\[(?P<end_time>[\d\.]+)\]\((?P<sender>\d+),\s*(?P<content>.*)\)')

def main(filename):
    content = open(filename, 'r').read().decode('utf-8','ignore')
    timelap = []
    start_times = []
    end_times = []
    msgsize = []
    outputObj = []
    import json

    for mat in infoExtractor.finditer(content):
        res = mat.groupdict()
        start_times.append(float(res['start_time']))
        end_times.append(float(res['end_time']))
        time_diff = float(res['end_time']) - float(res['start_time'])
        timelap.append(time_diff)
        msgsize.append(int(res['bytes']))
        outputObj.append([res['sender'], res['content'], '|'+str(float(res['start_time']))+'|', '|'+str(float(res['end_time']))+'|'])

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


if __name__=='__main__':
    main(sys.argv[1])
