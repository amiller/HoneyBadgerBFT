from pylab import *

# Measurements from the table
expt = [
    (8,2,[
        (512, 3.918, 2.849),
        (1024, 4.764, 3.740),
        (4096, 6.228, 5.108),
        (8192, 10.337, 9.128),
        (16384, 19.396, 18.705),
        (32768, 37.852, 36.618),
    ]),
    (16,4,[
        (1024,5.581,4.260),
        (2048,6.893,5.685),
        (4096,10.552,9.294),
        (8192,21.945,18.719),
        (16384,39.207,36.931)
    ]),
    (32,8,[
        (1024,8.599,7.152),
        (2048,13.139,11.434),
        (4096,22.405,20.767),
        (8192,46.093,43.609)
    ]),
    (64,16, [
        (512,19.670,14.531),
        (1024,22.933,19.871),
        (2048,53.125,29.110),
        (4096,81.278,55.204),
        (8192,171.143,158.949),
    ])]



def do_plot():
    close(1)
    figure(1, figsize=(7,5));
    clf()
    for N,t, entries in expt:
        throughput = []
        batch = []
        for ToverN, _, latency in entries:
            batch.append(N*ToverN/1000.)
            throughput.append(ToverN*(N-t) / latency)
        plot(batch, throughput, label='%d/%d' % (N,t))
    legend(title='Nodes/tolerance', loc='best')
    ylabel('Throughput (Tx per second)')
    xlabel('Requests  (Tx x1000)')
    tight_layout()
