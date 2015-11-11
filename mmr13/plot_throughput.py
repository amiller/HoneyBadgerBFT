import matplotlib.pyplot as plt

# Measurements from the table
expt = [
    (8,2,[
        # (512,5.96925),
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
        (1024, 105.0365)
    ])]



def do_plot():
    f = plt.figure(1, figsize=(7,5));
    plt.clf()
    ax = f.add_subplot(1, 1, 1)
    for N,t, entries in expt:
        throughput = []
        batch = []
        for ToverN, latency in entries:
            batch.append(N*ToverN)
            throughput.append(ToverN*(N-t) / latency)
        ax.plot(batch, throughput, label='%d/%d' % (N,t))
    ax.set_xscale("log")
    ax.set_yscale("log")
    plt.ylim([10**2.1, 10**3.8])
    plt.xlim([10**3.8, 10**6.1])
    plt.legend(title='Nodes / Tolerance', loc='best')
    plt.ylabel('Throughput (Tx per second)')
    plt.xlabel('Requests (Tx)')
    # plt.tight_layout()
    # plt.show()
    plt.savefig('plot_throughput.svg', format='svg', dpi=1000)

do_plot()
