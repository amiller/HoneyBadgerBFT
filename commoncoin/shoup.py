# Practical Threshold Signatures [Shoup2000]
# http://eprint.iacr.org/1999/011
#
# l: total number of parties
# k: number of shares required to obtain signature
# t: number of corruptible parties
#
# We only care about the case when k = t+1.

import random
import millerrabin
import gmpy2
import math
from fractions import gcd

# To generate safe primes: 
# $ openssl gendh 1024 | openssl dh -noout -text

# https://tools.ietf.org/html/draft-ietf-tls-srp-07#ref-MODP
safe_prime_1 = int(''.join("EEAF0AB9 ADB38DD6 9C33F80A FA8FC5E8 60726187 75FF3C0B 9EA2314C 9C256576 D674DF74 96EA81D3 383B4813 D692C6E0 E0D5D8E2 50B98BE4 8E495C1D 6089DAD1 5DC7D7B4 6154D6B6 CE8EF4AD 69B15D49 82559B29 7BCF1885 C529F566 660E57EC 68EDBC3C 05726CC0 2FD4CBF4 976EAA9A FD5138FE 8376435B 9FC61D2F C0EB06E3".split()),16)

from Crypto.Hash import SHA256
hash = lambda x: long(SHA256.new(x).hexdigest(),16)

safe_prime_2 = int(''.join("""
00:d7:3a:cf:a2:50:7d:13:45:56:5c:cb:7a:8b:55:
9d:3d:59:86:d0:01:58:e7:77:1b:11:6e:a8:a9:0f:
6e:cc:46:d6:c2:e8:b6:1d:78:0d:4d:62:78:1d:3f:
a2:2f:52:fc:6b:1b:47:61:68:4a:39:da:28:fd:d6:
bb:fb:72:a5:ea:c9:a1:aa:8f:74:83:6d:97:71:11:
82:ec:13:b8:28:b9:ea:ca:40:29:3c:7c:90:3e:a2:
91:c9:59:05:c9:a4:fc:1f:b7:57:03:67:c4:28:e7:
0c:7d:2c:d9:bb:bc:cf:1a:e3:4f:7f:05:95:5e:79:
7c:ac:63:6a:16:31:c5:01:2b""".replace(':','').split()),16)

def egcd(a, b):
    x,y, u,v = 0,1, 1,0
    while a != 0:
        q, r = b//a, b%a
        m, n = x-u*q, y-v*q
        b,a, x,y, u,v = a,r, u,v, m,n
    gcd = b
    return gcd, x, y

def generate_safe_prime(bits):
    while True:
        print 'trying prime'
        p_ = millerrabin.generateLargePrime(bits-1)
        if type(p_) is str: 
            print 'failed to find prime, trying again'
            continue
        p = 2*p_ + 1
        if millerrabin.is_probable_prime(p):
            return p
        else:
            'not a safe prime, trying again'

def random_Qn(n):
    # Generate a square in n
    x = random.randrange(0, n)
    return pow(x, 2, n)

def dealer(bits=2048, players=10, k=5):
    #random.seed(1203103)
    global n, m, p, q, e, d, shares
    assert bits == 2048, 'need different parameters'
    p = safe_prime_1
    q = safe_prime_2
    assert p.bit_length() == q.bit_length() == 1024

    n = p*q # RSA modulus
    m = (p-1)/2 * (q-1)/2

    trapdoors = dict(p=p, q=q)

    # Public exponent
    e = millerrabin.generateLargePrime(players.bit_length()+1) 

    # Compute d such that de == 1 mod m
    d = gmpy2.divm(1, e, m)
    assert (d*e) % m == 1

    public_key = (n,e)
    #print 'public_key', public_key

    trapdoor = dict(d=d, p=p, q=q)

    # Random polynomial coefficients
    a = [d]
    for i in range(1,k):
        a.append(random.randrange(0,m))
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
    SKs = []
    for i in range(1,players+1):
        SKs.append(f(i))

    # Random quadratic residue
    VK = v = random_Qn(n)

    # Verification keys
    VKs = []
    for i in range(players):
        VKs.append(gmpy2.powmod(v, SKs[i], n))

    public_key = ShoupPublicKey(n, e, players, k, VK, VKs)
    secret_keys = [ShoupPrivateKey(n, e, players, k, VK, VKs, SK, i) 
                   for i, SK in enumerate(SKs,start=1)]

    for i in [0]:
        S = set(range(1,k+1))
        lhs = (public_key.Delta() * f(i)) % m
        rhs = sum(public_key.lambdaS(S,i,j) * f(j) for j in S) % m
        assert lhs == rhs
        #print i, 'ok'

    return public_key, secret_keys

class ShoupPublicKey(object):
    def __init__(self, n, e, l, k, VK, VKs):
        self.n = n
        self.e = e
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
        assert (self.Delta()*num) % den == 0
        return self.Delta() * num / den

    def Delta(self):
        return math.factorial(self.l)

    def combine_shares(self, m, sigs):
        # sigs: a mapping from idx -> sig
        S = set(sigs.keys())
        assert S.issubset(range(1, self.l+1))

        x = hash(m)
        
        #def ppow(x, e, n):
        #    if e >= 0: return pow(x, e, n)
        #    else: 
        #        x_inv = long(gmpy.divm(1, x, n))
        #        r = pow(x_inv, -e, n)
        #        return r
        def ppow(x, e, n): return gmpy2.powmod(x,e,n)

        w = 1L
        for i,sig in sigs.iteritems():
            w = (w * ppow(sig, 2*self.lambdaS(S,0,i), self.n)) % self.n

        ep = 4*self.Delta()**2

        #assert pow(w, e, self.n) == pow(x, ep, self.n)
        assert gcd(ep, self.e) == 1

        _, a, b = egcd(ep, self.e)
        y = (ppow(w, a, self.n) * 
             ppow(x, b, self.n)) % self.n

        #assert self.verify_signature(y, m)
        return y

    def verify_signature(self, sig, m):
        y = sig
        x = hash(m)
        assert x == gmpy2.powmod(y, self.e, self.n)
        return True

class ShoupPrivateKey(ShoupPublicKey):
    def __init__(self, n, e, l, k, VK, VKs, SK, i):
        super(ShoupPrivateKey,self).__init__(n, e, l, k, VK, VKs)
        assert 1 <= i <= self.l
        self.i = i
        self.SK = SK

    def sign(self, m):
        # Generates a signature share on m
        x = hash(m)
        return gmpy2.powmod(x, 2*self.Delta()*self.SK, self.n)

def test():
    global PK, SKs
    PK, SKs = dealer(players=100,k=35)

    global sigs
    sigs = {}
    for SK in SKs:
        sigs[SK.i] = SK.sign('hi')

    SS = range(1,PK.l+1)
    for i in range(20):
        random.shuffle(SS)
        S = set(SS[:PK.k])
        sig = PK.combine_shares('hi', dict((s,sigs[s]) for s in S))
        assert PK.verify_signature(sig, 'hi')
