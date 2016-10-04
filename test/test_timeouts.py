from gevent import monkey
monkey.patch_all()

import gevent
from gevent import Greenlet
from gevent.queue import Queue
import random

import mmr13
reload(mmr13)
from mmr13 import *

class TimeoutException(Exception):
    pass

def test_join():
    q1 = Queue(1)
    q2 = Queue(2)

    def _run(q, n):
        gevent.sleep(random.random()*2)
        q.put(n)

    Greenlet(_run, q1, 'Item 1').start()
    Greenlet(_run, q2, 'Item 2').start()

    tag, firstItem = joinQueues(q1, q2)

    print 'firstItem:', firstItem
    if tag == 'a':
        print 'waiting for Item2:'
        print q2.get()
    if tag == 'b':
        print 'waiting for Item1:'
        print q1.get()

# Use joinQueue to implement wait or timeout
def getTimeout(b, t):
    a = Queue(1)
    def _timeout():
        gevent.sleep(t)
        a.put(None)
            
    Greenlet(_timeout).start()
    tag, item = joinQueues(a, b)
    if tag == 'a': raise TimeoutException
    return item

def test_timeout():
    q = Queue(1)
    def _run():
        t = random.random()
        print 'waiting %f seconds' % t
        gevent.sleep(t)
        q.put('Item A')
    Greenlet(_run).start()
    try:
        item = getTimeout(q, 0.5)
        print 'Item received', item
    except TimeoutException:
        print 'timed out'
