import subprocess, sys, signal

def runOnTransaction(N, t, Tx):
    p = subprocess.check_output(
        ['python', '-m', 'HoneyBadgerBFT.test.honest_party_test',
            '-k', '%d_%d.key' % (N, t), '-e', 'ecdsa.keys', '-b', '%d' % Tx,
            '-n', str(N), '-t', str(t), '-c', 'th_%d_%d.keys' % (N, t)],
        shell=False,
    )
    return p.split('Total Message size ')[1].strip()

    counter = 0
    sent = False
    while True:
        line = p.stdout.readline()
        if 'size' in line:
            return line.replace('Total Message size ','').strip()
        if line == '':
            break
        if 'synced' in line:
            counter += 1
        if counter >= N - t and not sent:
            p.send_signal(signal.SIGINT)
            sent = True

    
import sys
def main(N, t, start_i=0, end_i=11, start_j=0):
    for i in range(start_i, end_i):
        sys.stdout.write(str(2**i))
        for j in range(start_j, 4):
            sys.stdout.write(' ' + str(runOnTransaction(N, t, 2**i)))
        sys.stdout.write('\n')


if __name__=='__main__':
    if len(sys.argv) > 3:
        main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))    
    else:
        main(int(sys.argv[1]), int(sys.argv[2]))
