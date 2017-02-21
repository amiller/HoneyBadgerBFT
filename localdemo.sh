#!/bin/bash
# Assumes parameters in env variables:
# t: the number of faults
# N: number of nodes
# Generates configuration files
export t=1
export N=6
export B=16
python -m honeybadgerbft.commoncoin.generate_keys $N $(( t+1 )) > thsig$((N))_$((t)).keys
python -m honeybadgerbft.ecdsa.generate_keys_ecdsa $N > ecdsa.keys
python -m honeybadgerbft.threshenc.generate_keys $N $(( N-2*t )) > thenc$((N))_$((t)).keys
#python -m honeybadgerbft.test.honest_party_test -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys
#python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 0

tmux new-session    "python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 0; bash" \;  \
     splitw -h -p 67 "python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 1; bash" \;  \
     splitw -h -p 50 'python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 4; bash' \; \
     splitw -v -p 50 'python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 5; bash'  \; \
     selectp -t 0 \; \
     splitw -v -p 50 "python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 2; bash" \;  \
     selectp -t 2\; \
     splitw -v -p 50 "python -m honeybadgerbft.test.run_fifo -k thsig$((N))_$((t)).keys -e ecdsa.keys -b $B -n $N -t $t -c thenc$((N))_$((t)).keys -i 3; bash"
