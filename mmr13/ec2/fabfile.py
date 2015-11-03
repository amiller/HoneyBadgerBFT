from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib.files import append


def host_type():
    run('uname -s')


def cloneRepo():
    run('git clone https://github.com/amiller/HoneyBadgerBFT.git')

def install_dependencies():
    run('sudo apt-get update')
    run('sudo apt-get -y install python-gevent')
    run('sudo apt-get -y install git')
    run('sudo apt-get install python-socksipy')
    #run('sudo apt-get -y install python-pip')
    #run('sudo pip install SocksiPy')

@parallel
def stopProtocols():
    run('killall python')

def removeHosts():
    run('rm ~/hosts')

def writeHosts():
    append('~/hosts', open('hosts','r').read().split('\n'))

@parallel
def runProtocol():
    with cd('~/HoneyBadgerBFT/mmr13'):
        run('python honest_party_test_EC2.py ~/hosts')

def git_pull():
    with settings(warn_only=True):
        if run('test -d HoneyBadgerBFT').failed:
            run('git clone https://github.com/amiller/HoneyBadgerBFT.git')
    with cd('~/HoneyBadgerBFT'):
        run('git checkout another-dev')
        run('git pull')

