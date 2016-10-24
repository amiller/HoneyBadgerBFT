##########

import zfec
import time
import os
import math

def ceil(x):
    return int(math.ceil(x))

def testEncoder(N, t, buf, Threshold, enc):
    step = len(buf) % Threshold == 0 and len(buf) / Threshold or (len(buf) / Threshold + 1)
    buf = buf.ljust(step * Threshold, '\xFF')
    fragList = [buf[i*step:(i+1)*step] for i in range(Threshold)]
    return enc.encode(fragList)

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
            print N, t, 2**j, 'encode', time.time() - start
            start = time.time()
            zfecDecoder.decode(fragList[:Threshold], range(Threshold))
            print N, t, 2**j, 'decode', time.time() - start

main()