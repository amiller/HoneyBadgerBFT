__author__ = 'aluex'

import subprocess32 as subprocess
import sys, signal, time
#./honest_party_test_tor_multipleCircuits.py . 4_1.key ecdsa_keys 1 4 1
def runOnTransaction(N, t, Tx):
    # p = subprocess.Popen(
    retry = True
    while retry:
        try:
            p = subprocess.check_output(
                ['python', './honest_party_test_tor_multipleCircuits.py', 'lol', '%d_%d.key' % (N, t), 'ecdsa_keys', '%d' % Tx, str(N), str(t)],
                timeout = 30
                # stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                # stdin=subprocess.PIPE
            )
            retry = False
        except subprocess.TimeoutExpired:
            retry = True
            time.sleep(2)
    q = subprocess.check_output(['python', 'process.py', 'msglog.TorMultiple'])
    print N, t, Tx, q.replace('\n', ' ')

import sys
def main(N, t, start_i=0, end_i=11, start_j=0):
    for i in range(start_i, end_i):
        # sys.stdout.write(str(2**i))
        for j in range(start_j, 4):
            runOnTransaction(N, t, 2**i)
        print 


if __name__=='__main__':
    if len(sys.argv) > 3:
        main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    else:
        main(int(sys.argv[1]), int(sys.argv[2]))
