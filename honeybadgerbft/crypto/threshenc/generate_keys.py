from tpke import dealer, serialize, group
import argparse
import cPickle


def _generate_keys(players, k):
    if k:
        k = int(k)
    else:
        k = players / 2  # N - 2 * t
    PK, SKs = dealer(players=players, k=k)
    return (PK.l, PK.k, serialize(PK.VK), [serialize(VKp) for VKp in PK.VKs],
            [(SK.i, serialize(SK.SK)) for SK in SKs])


def main():
    """ """
    parser = argparse.ArgumentParser()
    parser.add_argument('players', help='The number of players')
    parser.add_argument('k', help='k')
    args = parser.parse_args()
    keys = _generate_keys(int(args.players), args.k)
    print cPickle.dumps(keys)


if __name__ == '__main__':
    main()
