FROM ubuntu:trusty

RUN apt-get update
RUN apt-get -y install python-gevent git wget python-pip python-dev python-gmpy2 flex bison libgmp-dev libssl-dev

RUN pip install PySocks pycrypto ecdsa zfec gipc nose2

RUN wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
RUN tar -xvf pbc-0.5.14.tar.gz
RUN cd pbc-0.5.14 && ./configure && make && make install

RUN git clone https://github.com/JHUISI/charm.git
RUN cd charm && git checkout 2.7-dev && ./configure.sh && python setup.py install

ENV SRC /usr/local/src/HoneyBadgerBFT
WORKDIR $SRC
ADD . $SRC/
CMD sh $SRC/start.sh
