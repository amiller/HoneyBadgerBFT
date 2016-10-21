#!/bin/bash
export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib 
python -m HoneyBadgerBFT.commoncoin.generate_keys $N $(( t+1 )) > thsig$((N))_$((t)).keys
python -m HoneyBadgerBFT.ecdsa.generate_keys_ecdsa $N > ecdsa.keys
python -m HoneyBadgerBFT.threshenc.generate_keys $N $(( N-2*t )) > thenc$((N))_$((t)).keys
python -m HoneyBadgerBFT.test.honest_party_test -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys
