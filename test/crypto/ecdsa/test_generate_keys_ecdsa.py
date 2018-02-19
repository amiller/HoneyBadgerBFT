from collections import namedtuple


def test_generate_key_list():
    from honeybadgerbft.crypto.ecdsa.generate_keys_ecdsa import generate_key_list
    keylist = generate_key_list(10)
    assert len(keylist) == 10


def test_main(monkeypatch):
    from honeybadgerbft.crypto.ecdsa.generate_keys_ecdsa import main

    def mock_parse_args(players):
        Args = namedtuple('Args', ('players',))
        args = Args(players)
        return args

    monkeypatch.setattr('argparse.ArgumentParser.parse_args', lambda s: mock_parse_args(10))
    main()
