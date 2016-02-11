#!/usr/bin/env python
# a stacked bar plot with errorbars
import numpy as np
import matplotlib.pyplot as plt

d = [
(8197320, 16389296, 32773320, 65541320, 131077320, 262149352, 524289312),
(16427008, 32811040, 65579048, 131115048, 262186976, 524331072, 1048611120),
(12720, 15360, 13680, 13680, 13680, 15360, 13680),
(12720, 15360, 13680, 13680, 13680, 15360, 13680),
(338352, 408576, 363888, 363888, 363888, 408576, 363888),
(20480, 20480, 20480, 20480, 20480, 20480, 20480)
]

N = 7
ind = np.arange(N)    # the x locations for the groups
width = 0.35       # the width of the bars: can also be len(x) sequence

p = []
for data in d:
    p.append(plt.bar(ind, data, width, color='r'))

plt.ylabel('Percent')
plt.title('Scores by group and gender')
plt.xticks(ind + width/2., map(lambda _: str(_), (512, 1024, 2048, 4096, 8192, 16384, 32768)))
plt.yticks(np.arange(0, 81, 10))
plt.legend((p1[0], p2[0]), ('Men', 'Women'))

plt.savefig('plot_msg_breakdown.pdf', format='pdf', dpi=1000)