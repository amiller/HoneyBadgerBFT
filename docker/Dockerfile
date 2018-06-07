FROM ubuntu:trusty
RUN apt-get update
RUN apt-get -y install python-gevent
RUN apt-get -y install git
RUN apt-get -y install wget
RUN apt-get -y install python-pip
RUN apt-get -y install python-dev
RUN apt-get -y install python-gmpy2
RUN apt-get -y install flex
RUN apt-get -y install bison
RUN apt-get -y install libgmp-dev
RUN apt-get -y install libssl-dev
RUN pip install --upgrade setuptools
RUN pip install --upgrade greenlet
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
RUN cd HoneyBadgerBFT && git checkout another-dev
COPY ./start.sh /
CMD sh /start.sh
