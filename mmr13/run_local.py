import subprocess, sys, signal

def runOnTransaction(N, t, Tx):
    p = subprocess.Popen(
        ['python', './honest_party_test.py', '%d_%d.key' % (N, t), 'ecdsa_keys', '%d' % (Tx * 62.5), str(N), str(t)],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )
    counter = 0
    while True:
        line = p.stdout.readline()
        if 'size' in line:
            # print Tx, line
            return line.replace('Total Message size ','').strip()
        print line, counter
        if line == '':
            break
        # print(line.strip())  # remove extra ws between lines
        if 'synced' in line:
            counter += 1
        if counter >= N - t:
            p.send_signal(signal.SIGINT)

    
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
