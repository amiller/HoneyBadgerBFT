__author__ = 'aluex'
from subprocess import check_output
import re

filter = re.compile(r'Total election: (?P<total>[\d]+), success election: (?P<success>[\d]+)')

dataset_total = []
dataset_success = []
dataset_ratio = []

for tMinI in range(1, 50, 1):
    for tMaxI in range(tMinI, 50, 1):
        tMin = tMinI / 100.0
        tMax = tMaxI / 100.0
        print tMin, tMax
        result = check_output(['./raft.py', '-v', '-1', '-m', str(tMin), '-M', str(tMax)])
        total, success = filter.findall(result)[0]
        dataset_total.append([tMin, tMax, int(total)])
        dataset_success.append([tMin, tMax, int(success)])
        dataset_ratio.append([tMin, tMax, float(int(success)) / int(total)])


def mathematica_list(l):
    return repr(l).replace('[', '{').replace(']', '}')

print mathematica_list(dataset_total)
print mathematica_list(dataset_ratio)
