FROM ubuntu:trusty
RUN apt-get update
RUN apt-get -y install python-gevent git wget python-pip python-dev python-gmpy2 flex bison libgmp-dev libssl-dev

RUN pip install PySocks
RUN pip install pycrypto
RUN pip install ecdsa
RUN pip install zfec
RUN pip install gipc

RUN wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
RUN tar -xvf pbc-0.5.14.tar.gz
RUN cd pbc-0.5.14 && ./configure && make && make install

RUN git clone https://github.com/JHUISI/charm.git
RUN cd charm && git checkout 2.7-dev && ./configure.sh && python setup.py install

RUN git clone https://github.com/amiller/HoneyBadgerBFT.git
RUN cd HoneyBadgerBFT && git checkout dev
COPY ./start.sh /
CMD sh /start.sh
