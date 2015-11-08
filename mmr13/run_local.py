import subprocess, sys

def runOnTransaction(N, t, Tx):
    p = subprocess.Popen(
        ['python', './honest_party_test.py', '%d_%d.key' % (N, t), 'ecdsa_keys', '%d' % (Tx * 62.5)],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE
    )
    counter = 0
    while True:
        line = p.stdout.readline()
        if line == '':
            break
        # print(line.strip())  # remove extra ws between lines
        if 'synced' in line:
            counter += 1
        if counter >= N - t:
            p.kill()
    print Tx, p.stdout.read()

def main(N, t):
    for i in range(11):
        runOnTransaction(N, t, 2**i)

if __name__=='__main__':
    main(int(sys.argv[1], sys.argv[2]))
