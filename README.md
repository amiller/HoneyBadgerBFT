# HoneyBadgerBFT
The Honey Badger of BFT Protocols

<img width=200 src="http://i.imgur.com/wqzdYl4.png"/>

Most fault tolerant protocols (including RAFT, PBFT, Zyzzyva, Q/U) don't guarantee good performance when there are Byzantine faults.
Even the so-called "robust" BFT protocols (like UpRight, RBFT, Prime, Spinning, and Stellar) have lots of hard-coded timeout parameters, and only guarantee performance when the network behaves as expected - hence they are mostly well-suited to corporate data centers.

HoneyBadgerBFT is fault tolerance for the *wild*. Bagder nodes stay hidden behind anonymizing relays like Tor, and the purely-asynchronous protocol makes progress at whatever rate the network provides. Bitcoin collateral deposits and trusted hardware (like Intel SGX) make attacking a HoneyBadgerBFT instance expensive and unprofitable.
