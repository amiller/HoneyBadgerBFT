#!/bin/bash
killall -9 node

declare -A baseport    # These must be kept up to date with contlist!
baseport[mnt224]=9000
baseport[ss512]=9500

DKG=$PWD/dkg/DKG_0.8.0/DKG-Executable/

declare -A launch
for curve in mnt224 ss512
do
  for x in `seq 1 4`
  do
    rm -r $DKG/$curve/node$x
    mkdir -p $DKG/$curve/node$x
    ln -s $DKG/../src/node $DKG/$curve/node$x/
    ln -s $DKG/certs $DKG/$curve/node$x/
    ln -s $DKG/$curve.contlist $DKG/$curve/node$x/contlist
    ln -s $DKG/$curve.system.param $DKG/$curve/node$x/system.param
    ln -s $DKG/$curve.pairing.param $DKG/$curve/node$x/pairing.param
    launch["$curve:$x"]="pushd $DKG/$curve/node$x; bash -c \"./node $((${baseport[$curve]}+$x)) certs/$x.pem certs/$x-key.pem contlist 0 0 0&\"; popd"
    echo ${launch["$curve:$x"]}
  done
done

tmux new-session    "${launch[mnt224:1]}; ${launch[ss512:1]}; python run_fifo.py -i 1; bash" \;  \
     splitw -h -p 67 "${launch[mnt224:2]}; ${launch[ss512:2]}; python run_fifo.py -i 2; bash" \;  \
     splitw -h -p 50 "bash -c \"python echosock.py&\"; cd go-ethereum; ./build/bin/geth --datadir gdata --networkid 10 init genesis.json; env BADGER_SOCK=/tmp/hb GETH_SOCK=/tmp/gethsock ./build/bin/geth --datadir gdata --networkid 10 --password \"\" --unlock 0 console; bash" \;  \
     splitw -v -p 50 "bash" \;  \
     selectp -t 0 \; \
     splitw -v -p 50 "${launch[mnt224:3]}; ${launch[ss512:3]}; python run_fifo.py -i 3; bash" \;  \
     selectp -t 2\; \
     splitw -v -p 50 "${launch[mnt224:4]}; ${launch[ss512:4]}; python run_fifo.py -i 4; bash"
