##########

import zfec
import time
import os
import math

def ceil(x):
    #assert isinstance(x, float)
    #if int(x) != x:
    #    return int(x)+1
    #return int(x)
    return int(math.ceil(x))

def testEncoder(N, t, buf, Threshold, enc):
    step = len(buf) % Threshold == 0 and len(buf) / Threshold or (len(buf) / Threshold + 1)
    buf = buf.ljust(step * Threshold, '\xFF')
    fragList = [buf[i*step:(i+1)*step] for i in range(Threshold)]
    return zfecEncoder.encode(fragList)

def main():
    for i in range(2, 8):
        N = 2**i
        t = 2**(i-2)
        Threshold = ceil((N-t+1)/2.0)
        zfecEncoder = zfec.Encoder(Threshold, N)
        zfecDecoder = zfec.Decoder(Threshold, N)
        for j in range(9, 12):
            Tx = os.urandom((2**j) * 250)
            start = time.time()
            fragList = testEncoder(N, t, Tx, Threshold, zfecEncoder)
            print N, t, Tx, 'encode', time.time() - start
            start = time.time()
            zfecDecoder.decode(fragList[:Threshold], range(Threshold))
            print N, t, Tx, 'decode', time.time() - start

main()