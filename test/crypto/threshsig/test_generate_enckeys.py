from collections import namedtuple

from pytest import mark


@mark.parametrize('k', (None, 3))
def test_generate_keys(k):
    from honeybadgerbft.crypto.threshenc.generate_keys import _generate_keys
    keys = _generate_keys(10, k)
    assert len(keys) == 5


def test_main(monkeypatch):
    from honeybadgerbft.crypto.threshenc.generate_keys import main

    def mock_parse_args(players, k):
        Args = namedtuple('Args', ('players', 'k'))
        args = Args(players, k)
        return args

    monkeypatch.setattr('argparse.ArgumentParser.parse_args', lambda s: mock_parse_args(10, 4))
    main()
