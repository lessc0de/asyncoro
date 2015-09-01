# Run 'discoronode.py' program to start processes to execute
# computations sent by this client, along with this program.

# Example where this client sends computation to remote discoro
# process to run as remote coroutines. Remote coroutines and client
# can use message passing to exchange data.

import sys, logging, random
import asyncoro.discoro as discoro
from asyncoro.discoro import StatusMessage
import asyncoro.disasyncoro as asyncoro

# objects of C are exchanged between client and servers
class C(object):
    def __init__(self, i):
        self.i = i
        self.n = None

    def __repr__(self):
        return '%d: %s' % (self.i, self.n)

# this generator function is sent to remote discoro servers to run
# coroutines there
def compute(obj, client, coro=None):
    # obj is an instance of C
    import math
    yield coro.sleep(obj.n)

# status messages indicating nodes, processes as well as remote
# coroutines finish status are sent to this coroutine
def status_proc(coro=None):
    coro.set_daemon()
    while True:
        msg = yield coro.receive()
        http_server.status_coro.send(msg)
        if isinstance(msg, asyncoro.MonitorException):
            if msg.args[1][0] != StopIteration:
                print('rcoro %s failed: %s / %s' % (msg.args[0], msg.args[1][0], msg.args[1][1]))
        elif isinstance(msg, StatusMessage):
            if msg.status == discoro.Scheduler.CoroCreated:
                print('rcoro %s started' % msg.info.coro)
            else:
                print('Status: %s / %s' % (msg.status, msg.info))

        else:
            print('status msg ignored: %s' % type(msg))

def client_proc(computation, coro=None):
    # scheduler sends node / process status messages to status_coro
    computation.status_coro = asyncoro.Coro(status_proc)

    # distribute computation to server
    if (yield computation.schedule()):
        raise Exception('schedule failed')

    i = 0
    while True:
        if (yield coro.receive()) is None:
            break
        i += 1
        c = C(i)
        c.n = random.uniform(50, 90)
        rcoro = yield computation.run(compute, c, coro)
        if isinstance(rcoro, asyncoro.Coro):
            pass
        else:
            print('failed to create remote coroutine for %s: %s' % (c, rcoro))

    yield computation.close()

if __name__ == '__main__':
    import os, threading, httpd
    asyncoro.logger.setLevel(logging.DEBUG)
    # if scheduler is not already running (on a node as a program),
    # start it (private scheduler):
    discoro.Scheduler()
    # send generator function and class C (as the computation uses
    # objects of C)
    http_server = httpd.HTTPServer()
    computation = discoro.Computation([compute, C])
    coro = asyncoro.Coro(client_proc, computation)
    # each time anything other than 'quit' or 'exit' is entered, new
    # coroutine is scheduled
    while True:
        cmd = sys.stdin.readline().strip().lower()
        if cmd == 'quit' or cmd == 'exit':
            coro.send(None)
            break
        else:
            coro.send('new')
