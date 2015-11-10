__author__ = 'aluex'

import subprocess, sys, signal
#./honest_party_test_tor_multipleCircuits.py . 4_1.key ecdsa_keys 1 4 1
def runOnTransaction(N, t, Tx):
    # p = subprocess.Popen(
    p = subprocess.check_output(
        ['python', './honest_party_test_tor_multipleCircuits.py', 'lol', '%d_%d.key' % (N, t), 'ecdsa_keys', '%d' % Tx, str(N), str(t)],
        # stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )
    q = subprocess.check_output(['python', 'process.py', 'msglog.TorMultiple'])
    print q.replace('\n', ' ')
    return 
    counter = 0
    sent = False
    while True:
        line = p.stdout.readline()
        if 'size' in line:
            # print Tx, line
            return line.replace('Total Message size ','').strip()
        if line == '':
            break
        # print(line.strip())  # remove extra ws between lines
        if 'synced' in line:
            counter += 1
        if counter >= N - t and not sent:
            p.send_signal(signal.SIGINT)
            sent = True
            # print 'signal sent'
        # print line, counter
    q = subprocess.check_output(['python', 'process.py', 'msglog.TorMultiple'])
    print q.replace('\n', ' ')

import sys
def main(N, t, start_i=0, end_i=11, start_j=0):
    for i in range(start_i, end_i):
        sys.stdout.write(str(2**i))
        for j in range(start_j, 4):
            runOnTransaction(N, t, 2**i)
        sys.stdout.write('\n')


if __name__=='__main__':
    if len(sys.argv) > 3:
        main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    else:
        main(int(sys.argv[1]), int(sys.argv[2]))
