# HoneyBadgerBFT
The Honey Badger of BFT Protocols

<img width=200 src="http://i.imgur.com/wqzdYl4.png"/>

Most fault tolerant protocols (including RAFT, PBFT, Zyzzyva, Q/U) don't guarantee good performance when there are Byzantine faults.
Even the so-called "robust" BFT protocols (like UpRight, RBFT, Prime, Spinning, and Stellar) have various hard-coded timeout parameters, and can only guarantee performance when the network behaves approximately as expected - hence they are best suited to well-controlled settings like corporate data centers.

HoneyBadgerBFT is fault tolerance for the wild wild wide-area-network. HoneyBadger nodes can even stay hidden behind anonymizing relays like Tor, and the purely-asynchronous protocol will make progress at whatever rate the network supports.

### License
This is released under the CARPL academic license. See ./CRAPL-LICENSE.txt
Other licenses may be issued at the authors' discretion.

### Docker

Build the docker image first.

    cd docker
    docker build -t honeybadgerbft .

Then for example you want to run an instance with N=8, t=2 and B=16:

    docker run -e N="8" -e t="2" -e B="16" -it honeybadgerbft

If you see "Concensus Finished" and some message statistics, the consensus is successful. Due to some issues of gevent with threading, there will be a "Exception KeyError" at the end of the program, please just ignore it.

### Docker with Multiple Containers

Make sure you have built your docker image first:

    cd docker
    docker build -t honeybadgerbft .

We provide a script to generate a docker-compose.yml for you to run test HoneyBadgerBFT on **N** containers.

	python docker_compose_gen.py N t B > docker-compose.yml
	
where N, t, B are parameters. For example,

	python docker_compose_gen.py 4 1 8 > docker-compose.yml
	
Then run your docker-compose. (Currently we let each container sleep for a second in order for the keys to become stable. Later we will fix this.)

	docker-compose down && docker-compose up

If you see at least **N-t** messages like 

	[4] 10 distinct tx synced and 6 tx left in the pool.
	
then the consensus is finished.

### Installation && How to run the code

Working directory is usually the **parent directory** of HoneyBadgerBFT. All the bold vars are experiment parameters:

+ **N** means the total number of parties;
+ **t** means the tolerance, usually N/4 in our experiments;
+ **B** means the maximum number of transactions committed in a block (by default N log N). And therefore each party proposes B/N transactions.

#### Install dependencies (maybe it is faster to do a snapshot on EC2 for these dependencies)
pbc


    wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
    tar -xvf pbc-0.5.14.tar.gz
    cd pbc-0.5.14
    ./configure ; make ; sudo make install
    export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/lib
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

charm


    sudo apt-get install python3-dev
    git clone https://github.com/JHUISI/charm.git
    cd charm
    git checkout 2.7-dev
    sudo python setup.py install



pycrypt


    sudo python -m pip install pycrypto

Clone the code:

    git clone https://github.com/amiller/HoneyBadgerBFT.git
    git checkout another-dev

Generate the keys
+ Threshold Signature Keys

    python -m HoneyBadgerBFT.commoncoin.generate_keys N (t+1) > thsigN_t.keys

+ ECDSA Keys

    python -m HoneyBadgerBFT.ecdsa.generate_keys_ecdsa N > ecdsa.keys

Threshold Encryption Keys

    python -m HoneyBadgerBFT.threshenc.generate_keys N (N-2t) > thencN_t.keys

Usually, we run ecdsa key generation with large N just once because it can be re-used for different N/t.
And we can store threshold signature keys and threshold encryption keys into different files for convenience.

##### Launch the code
    python -m HoneyBadgerBFT.test.honest_party_test -k thsigN_t.keys -e ecdsa.keys -b B -n N -t t -c thencN_t.keys

Notice that each party will expect at least NlgN many transactions. And usually there is a key exception after they finish the consensus. Please just ignore it.

### How to deploy the Amazon EC2 experiment

At HoneyBadger/ec2/ folder, run

    python utility.py [ec2_access_key] [ec2_secret_key]

In this interactive ipython environment, run the following:

+ Prepare the all the keys files and put them in your local directory (namely ec2 folder)
	
	(See the instructions above)

+ Launch new machines
        
        launch_new_instances(region, number_of_machine)

+ Query IPs

        ipAll()

+ Synchronize keys
    
        c(getIP(), 'syncKeys')

+ Install Dependencies
    
        c(getIP(), 'install_dependencies')

+ Clone and repo

    	c(getIP(), 'git_pull')

+ Launch the experiment

    	c(getIP(), 'runProtocol:N,t,B')
where N, t, B are experiment parameters (replace them with numbers).

### Unit Tests

TBA

