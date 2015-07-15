__author__ = 'aluex'

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import sys

filename = sys.argv[1]

data = open(filename, 'r').read().replace('{','[').replace('}',']').replace('\n','').split(']]')
datalist_total = eval(data[0]+']]')
datalist_ratio = eval(data[1]+']]')

fig_total = plt.figure()
ax_total = fig_total.add_subplot(111, projection='3d')

fig_ratio = plt.figure()
ax_ratio = fig_ratio.add_subplot(111, projection='3d')

for l in datalist_total:
    ax_total.scatter(l[0], l[1], l[2])
for l in datalist_ratio:
    ax_ratio.scatter(l[0], l[1], l[2])

if True:
    ax_total.set_xlabel('X Label')
    ax_total.set_ylabel('Y Label')
    ax_total.set_zlabel('Z Label')

if True:
    ax_ratio.set_xlabel('X Label')
    ax_ratio.set_ylabel('Y Label')
    ax_ratio.set_zlabel('Z Label')

fig_ratio.show()
fig_total.show()

raw_input()
