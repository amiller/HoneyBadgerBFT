import argparse
import cPickle
from ..core.utils import encodeTransaction, randomTransaction
import random


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('n', help='The number of transactions')
    parser.add_argument('seed', help='seed')
    args = parser.parse_args()
    ntx = int(args.n)
    if args.seed:
        seed = int(args.seed)
    else:
        seed = 123
    rnd = random.Random(seed)
    print "Random transaction generator fingerprints %s" % (hex(rnd.getrandbits(32*8)))
    transactionSet = set([encodeTransaction(randomTransaction(rnd), randomGenerator=rnd) for trC in range(ntx)])  # we are using the same one
    print cPickle.dumps(transactionSet)

if __name__ == '__main__':
    main()
