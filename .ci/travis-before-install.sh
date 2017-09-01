#!/bin/bash

if [ "${BUILD}" != "flake8" ]; then
    apt-get update -qq
    apt-get -y install flex bison libgmp-dev libmpc-dev python-dev libssl-dev
    wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
    tar -xvf pbc-0.5.14.tar.gz
    cd pbc-0.5.14 
    ./configure
    make
    make install
    cd ..
fi
