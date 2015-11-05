from ecdsa_ssl import *
import argparse
import cPickle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('players', help='The number of players');
    parser.add_argument('k', help='k');
    args = parser.parse_args()
    players = int(args.players)
    keylist = []
    for i in range(players):
        key = KEY()
        keylist.append(key.get_secret())
    print cPickle.dumps(keylist)

if __name__ == '__main__':
    main()