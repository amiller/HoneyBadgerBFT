from tpke import dealer, serialize, group
import argparse
import cPickle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('players', help='The number of players')
    parser.add_argument('k', help='k')
    args = parser.parse_args()
    players = int(args.players)
    if args.k:
        k = int(args.k)
    else:
        k = players / 2  # N - 2 * t
    PK, SKs = dealer(players=players, k=k)
    content = (PK.l, PK.k, serialize(PK.VK), [serialize(VKp) for VKp in PK.VKs],
               [(SK.i, serialize(SK.SK)) for SK in SKs])
    print cPickle.dumps(content)

if __name__ == '__main__':
    main()
    