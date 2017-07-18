FROM ubuntu:trusty

# Default cluster arguments. Override with "-e"
#
# total number of parties:
ENV N 8
# tolerance, usually N/4 in our experiments:
ENV t 2
# maximum number of transactions committed in a block:
ENV B 16

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get update
RUN apt-get -y install python-gevent git wget python-pip python-dev python-gmpy2 flex bison libgmp-dev libssl-dev

RUN pip install PySocks pycrypto ecdsa zfec gipc nose2 ethereum

RUN wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
RUN tar -xvf pbc-0.5.14.tar.gz
RUN cd pbc-0.5.14 && ./configure && make && make install

RUN git clone https://github.com/JHUISI/charm.git
RUN cd charm && git checkout 2.7-dev && ./configure.sh && python setup.py install

RUN apt-get -y install libgmp-dev libgnutls-dev tmux curl
RUN curl -O https://storage.googleapis.com/golang/go1.8.linux-amd64.tar.gz
RUN tar -xvf go1.8.linux-amd64.tar.gz
RUN mv go /usr/local
RUN mkdir /go
ENV GOPATH /go
ENV GOROOT /usr/local/go
ENV PATH $PATH:/usr/local/go/bin:/go/bin
RUN go version

ENV SRC /usr/local/src/HoneyBadgerBFT
WORKDIR /usr/local/src/
RUN git clone https://github.com/amiller/honeybadgerbft --branch demo3 HoneyBadgerBFT
WORKDIR $SRC


RUN git clone https://github.com/joelburget/go-ethereum #10001
WORKDIR go-ethereum
RUN make geth
#RUN go get ./cmd/geth

ENV LIBRARY_PATH /usr/local/lib
ENV LD_LIBRARY_PATH /usr/local/lib

WORKDIR $SRC
RUN mkdir dkg
WORKDIR dkg
RUN git clone https://github.com/amiller/distributed-keygen DKG_0.8.0

WORKDIR $SRC/dkg/DKG_0.8.0/PBC
RUN make clean && make
WORKDIR $SRC/dkg/DKG_0.8.0/src
RUN make clean && make

WORKDIR $SRC/
# Now add scripts that may change
ADD ./run_fifo.py $SRC/
ADD ./launch-4.sh $SRC/
ADD ./echosock.py $SRC/
ADD ./keystore $SRC/go-ethereum/gdata/keystore/

# Run tests by default
CMD $SRC/launch-4.sh
