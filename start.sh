#!/bin/bash

python -m honeybadgerbft.crypto.threshsig.generate_keys $N $(( t+1 )) > thsig$((N))_$((t)).keys
python -m honeybadgerbft.crypto.ecdsa.generate_keys_ecdsa $N >ecdsa.keys
python -m honeybadgerbft.crypto.threshenc.generate_keys $N $(( N-2*t )) > thenc$((N))_$((t)).keys

# FIXME: this is outdated:
python -m experiments.honest_party_test -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys
