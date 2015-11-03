from __future__ import with_statement
from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib.files import append

@parallel
def host_type():
    run('uname -s')

@parallel
def cloneRepo():
    run('git clone https://github.com/amiller/HoneyBadgerBFT.git')

@parallel
def install_dependencies():
    run('sudo apt-get update')
    run('sudo apt-get -y install python-gevent')
    run('sudo apt-get -y install git')
    run('sudo apt-get -y install subversion')
    run('sudo apt-get install python-socksipy')
    run('sudo apt-get -y install python-pip')
    run('sudo apt-get -y install python-dev')
    run('sudo apt-get -y install dtach')
    run('sudo pip install pycrypto')
    run('sudo pip install ecdsa')

@parallel
def stopProtocols():
    with settings(warn_only=True):
        run('killall python')
        run('killall dtach')
        run('killall server.py')

@parallel
def removeHosts():
    run('rm ~/hosts')

@parallel
def writeHosts():
    append('~/hosts', open('hosts','r').read().split('\n'))

@parallel
def runProtocol():
    with cd('~/HoneyBadgerBFT/mmr13'):
        run('python honest_party_test_EC2.py ~/hosts')

@parallel
def checkout():
    run('svn checkout --username aluex --password JkJ-3pc-s3Y-prp https://subversion.assembla.com/svn/ktc-scratch/')

@parallel
def svnUpdate():
    with settings(warn_only=True):
        if run('test -d ktc-scratch').failed:
            run('svn checkout --username aluex --password JkJ-3pc-s3Y-prp https://subversion.assembla.com/svn/ktc-scratch/')
    with cd('~/ktc-scratch'):
        run('svn up --username aluex --password JkJ-3pc-s3Y-prp')

@parallel
def svnClean():
    with settings(warn_only=True):
        if run('test -d ktc-scratch').failed:
            run('svn checkout --username aluex --password JkJ-3pc-s3Y-prp https://subversion.assembla.com/svn/ktc-scratch/')
    with cd('~/ktc-scratch'):
        run('svn cleanup')

@parallel
def makeExecutable():
    with cd('~/ktc-scratch'):
        run('chmod +x server.py')

# http://stackoverflow.com/questions/8775598/start-a-background-process-with-nohup-using-fabric
def runbg(cmd, sockname="dtach"):  
    return run('dtach -n `mktemp -u /tmp/%s.XXXX` %s'  % (sockname,cmd))

@parallel
def startPBFT(): ######## THIS SHOULD BE CALLED IN REVERSED HOST ORDER
    with cd('~/ktc-scratch'):
        run('python server.py')
        #run('sleep 10')

def startClient():
    with cd('~/ktc-scratch'):
        run('python gen_requests.py 1000')
        run('python client.py 1000')
        run('python parse_client_log.py')

def git_pull():
    with settings(warn_only=True):
        if run('test -d HoneyBadgerBFT').failed:
            run('git clone https://github.com/amiller/HoneyBadgerBFT.git')
    with cd('~/HoneyBadgerBFT'):
        run('git checkout another-dev')
        run('git pull')

