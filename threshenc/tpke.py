from charm.toolbox.pairinggroup import PairingGroup,ZR,G1,G2,GT,pair
from base64 import encodestring, decodestring
import random
from Crypto.Hash import SHA256
from Crypto import Random
from Crypto.Cipher import AES

# Threshold encryption based on Gap-Diffie-Hellman
# - Only encrypts messages that are 32-byte strings
# - For use in hybrid encryption schemes - first encrypt
#   a random key, use the key for symmetric AES

# Baek and Zheng 
# http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.119.1717&rep=rep1&type=pdf


# Dependencies: Charm, http://jhuisi.github.io/charm/
#         a wrapper for PBC (Pairing based crypto)


group = PairingGroup('SS512')
#group = PairingGroup('MNT224')

def serialize(g):
    # Only work in G1 here
    return decodestring(group.serialize(g)[2:])

def deserialize0(g):
    # Only work in G1 here
    return group.deserialize('0:'+encodestring(g))

def deserialize1(g):
    # Only work in G1 here
    return group.deserialize('1:'+encodestring(g))

def deserialize2(g):
    # Only work in G1 here
    return group.deserialize('2:'+encodestring(g))

def xor(x,y):
    assert len(x) == len(y) == 32
    return ''.join(chr(ord(x_)^ord(y_)) for x_,y_ in zip(x,y))

g1 = group.hash('geng1', G1)
g1.initPP()
g2 = g1
#g2 = group.hash('geng2', G2)
#g2.initPP()
ZERO = group.random(ZR)*0
ONE = group.random(ZR)*0+1

def hashG(g):
    return SHA256.new(serialize(g)).digest()

def hashH(g, x):
    assert len(x) == 32
    return group.hash(serialize(g) + x, G2)

class TPKEPublicKey(object):
    def __init__(self, l, k, VK, VKs):
        self.l = l
        self.k = k
        self.VK = VK
        self.VKs = VKs

    def lagrange(self, S, j):
        # Assert S is a subset of range(0,self.l)
        assert len(S) == self.k
        assert type(S) is set
        assert S.issubset(range(0,self.l))
        S = sorted(S)

        assert j in S
        assert 0 <= j < self.l
        mul = lambda a,b: a*b
        num = reduce(mul, [0 - jj - 1 for jj in S if jj != j], ONE)
        den = reduce(mul, [j - jj     for jj in S if jj != j], ONE)
        return num / den

    def encrypt(self, m):
        # Only encrypt 32 byte strings
        assert len(m) == 32
        #print '1'
        r = group.random(ZR)
        #print '2'
        U = g1 ** r
        #print '3'
        #V = xor(m, hashG(pair(g1, self.VK ** r)))
        #V = xor(m, hashG(pair(g1, self.VK ** r)))
        V = xor(m, hashG(self.VK ** r))
        #print '4'
        W = hashH(U, V) ** r
        #print '5'
        C = (U, V, W)
        return C

    def verify_ciphertext(self, (U, V, W)):
        # Check correctness of ciphertext
        H = hashH(U, V)
        assert pair(g1, W) == pair(U, H)
        return True

    def verify_share(self, i, U_i, (U,V,W)):
        assert 0 <= i < self.l
        Y_i = self.VKs[i]
        assert pair(U_i, g2) == pair(U, Y_i)
        return True

    def combine_shares(self, (U,V,W), shares):
        # sigs: a mapping from idx -> sig
        S = set(shares.keys())
        assert S.issubset(range(self.l))

        # ASSUMPTION
        # assert self.verify_ciphertext((U,V,W))

        mul = lambda a,b: a*b
        res = reduce(mul, 
                     [share ** self.lagrange(S, j)
                      for j,share in shares.iteritems()], ONE)
        return xor(hashG(res), V)


class TPKEPrivateKey(TPKEPublicKey):
    def __init__(self, l, k, VK, VKs, SK, i):
        super(TPKEPrivateKey,self).__init__(l, k, VK, VKs)
        assert 0 <= i < self.l
        self.i = i
        self.SK = SK

    def decrypt_share(self, (U, V, W)):
        # ASSUMPTION
        # assert self.verify_ciphertext((U,V,W))

        # H = hashH(U, V)
        # print U, V, W
        # print U
        # print self.SK
        U_i = U ** self.SK

        return U_i
        

def dealer(players=10, k=5):
    # Random polynomial coefficients
    secret = group.random(ZR)
    a = [secret]
    for i in range(1,k):
        a.append(group.random(ZR))
    assert len(a) == k

    # Polynomial evaluation
    def f(x):
        y = ZERO
        xx = ONE
        for coeff in a:
            y += coeff * xx
            xx *= x
        return y

    # Shares of master secret key
    SKs = [f(i) for i in range(1,players+1)]
    assert f(0) == secret

    # Verification keys
    VK = g2 ** secret
    VKs = [g2 ** xx for xx in SKs]

    public_key = TPKEPublicKey(players, k, VK, VKs)
    private_keys = [TPKEPrivateKey(players, k, VK, VKs, SK, i)
                    for i, SK in enumerate(SKs)]

    # Check reconstruction of 0
    S = set(range(0,k))
    lhs = f(0)
    rhs = sum(public_key.lagrange(S,j) * f(j+1) for j in S)
    assert lhs == rhs
    #print i, 'ok'

    return public_key, private_keys


def test():
    global PK, SKs
    PK, SKs = dealer(players=100,k=35)

    m = SHA256.new('how').digest()
    C = PK.encrypt(m)

    assert PK.verify_ciphertext(C)

    shares = [sk.decrypt_share(C) for sk in SKs]
    for i,share in enumerate(shares):
        assert PK.verify_share(i, share, C)

    SS = range(PK.l)
    for i in range(1):
        random.shuffle(SS)
        S = set(SS[:PK.k])
        
        m_ = PK.combine_shares(C, dict((s,shares[s]) for s in S))
        assert m_ == m



## Symmetric cryptography. Use AES with a 32-byte key

BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS) 
unpad = lambda s : s[:-ord(s[len(s)-1:])]

def encrypt( key, raw ):
    assert len(key) == 32
    raw = pad(raw)
    iv = Random.new().read( AES.block_size )
    cipher = AES.new( key, AES.MODE_CBC, iv )
    return ( iv + cipher.encrypt( raw ) ) 

def decrypt( key, enc ):
    enc = (enc)
    iv = enc[:16]
    cipher = AES.new( key, AES.MODE_CBC, iv )
    return unpad(cipher.decrypt( enc[16:] ))
