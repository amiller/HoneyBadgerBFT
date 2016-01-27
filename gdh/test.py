from charm.toolbox.pairinggroup import PairingGroup,ZR,G1,G2,GT,pair
from charm.toolbox.pairinggroup import serialize as serialize_charm, deserialize as deserialize_charm

from base64 import encodestring, decodestring

def serialize(g):
    # Only work in G1 here
    return decodestring(serialize_charm(g)[2:])

group = PairingGroup('SS512')

g = group.random(G1)
h = group.random(G1)
i = group.random(G1)

j = g * h
k = i ** group.random(ZR)
t = (j ** group.random(ZR)) / h

class TBLSPublicKey(object):
    def __init__(self, l, k, VK, VKs):
        self.l = l
        self.k = k
        self.VK = VK
        self.VKs = VKs

    def lambdaS(self, S, i, j):
        # Assert S is a subset of range(0,self.l)
        assert len(S) == self.k
        assert type(S) is set
        assert S.issubset(range(1,self.l+1))
        S = sorted(S)

        assert i not in S
        assert 0 <= i <= self.l
        assert j in S
        assert 1 <= j <= self.l
        mul = lambda a,b: a*b
        num = reduce(mul, [i - jj for jj in S if jj != j], 1)
        den = reduce(mul, [j - jj for jj in S if jj != j], 1)
        assert num % den == 0
        return num / den


class TBLSPrivateKey(TBLSPublicKey):
    def __init__(self, l, k, VK, VKs, SK, i):
        super(TBLSPrivateKey,self).__init__(l, k, VK, VKs)
        assert 1 <= i <= self.l
        self.i = i
        self.SK = SK


def dealer(players=10, k=5):
    # Random polynomial coefficients
    secret = group.random(ZR)
    a = [secret]
    for i in range(1,k):
        a.append(group.random(ZR))
    assert len(a) == k

    # Polynomial evaluation
    def f(x):
        y = 0
        xx = 1
        for coeff in a:
            y += coeff * xx
            xx *= x
        return y

    # Shares of master secret key
    SKs = [f(i) for i in range(1,players+1)]
    assert f(0) == secret

    # Verification keys
    VK = g ** secret
    VKs = [g ** xx for xx in a]

    public_key = TBLSPublicKey(players, k, VK, VKs)
    private_keys = [TBLSPrivateKey(players, k, VK, VKs, SK, i)
                    for i, SK in enumerate(SKs,start=1)]

    # Check reconstruction of 0
    for i in [0]:
        S = set(range(1,k+1))
        lhs = f(i)
        rhs = sum(public_key.lambdaS(S,i,j) * f(j) for j in S)
        assert lhs == rhs
        #print i, 'ok'


# Ok, begin implementing...


