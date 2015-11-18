# This example uses status messages and message passing to run 'setup'
# coroutine at remote process to prepare it for processing jobs.

# DiscoroStatus must be imported in global scope as below; otherwise,
# unserializing status messages fails (if external scheduler is used)
from asyncoro.discoro import DiscoroStatus
import asyncoro.discoro as discoro
import asyncoro.disasyncoro as asyncoro


# discoronode expects user computations to be generator functions (to
# create coroutines) that will 'yield' within pulse_interval (default
# 10 seconds). Otherwise, the daemon coroutine that sends pulse
# messages to scheduler will not get a chance to do so, causing
# scheduler to assume the node may be unreachable and abandon the
# computation. In this example, user computations are executed in
# threads, using AsyncThreadPool. The computation is simulated with
# 'time.sleep'. (Note that 'time.sleep' shouldn't be used in
# coroutines, as this will block entire asyncoro framework.)  This
# function sends message to client when the setup is done and then
# waits for (client's) message to cleanup.
def proc_setup(client, coro=None):
    global time, thread_pool # 'thread_pool' used in rcoro_proc
    import time
    # in this case at most one computation (rcoro_proc) runs, so pool
    # is created with 1 thread
    thread_pool = asyncoro.AsyncThreadPool(1)
    if (yield client.deliver('ready', timeout=10)) == 1:
        # data will be kept in memory until 'cleanup' is received
        msg = yield coro.receive()
        # assert msg == 'cleanup'
    thread_pool.terminate()


# This generator function is sent to remote discoro process to run
# coroutines there. Note that compute_proc and proc_setup run in the
# same process (and share same address space), so global variables are
# shared (updates in one coroutine are visible in other coroutnies in
# the same process).
def compute_proc(n, coro=None):
    # execute 'time.sleep' with thread_pool initialized in proc_setup
    def thread_proc():
        time.sleep(n)
        return n # result

    yield thread_pool.async_task(thread_proc)
    # return value from thread_proc is sent as result (with MonitorException)

def client_proc(computation, njobs, coro=None):
    cleanup_rcoros = set() # processes used are kept track to cleanup when done
    status = {'submitted': 0, 'done': 0}

    # client coroutine to setup a remote process (with proc_setup coroutine)
    # then submits a job
    def init_proc(where, coro=None):
        rcoro = yield computation.run_at(where, proc_setup, coro)
        if isinstance(rcoro, asyncoro.Coro):
            # wait till coroutine has read data in to memory
            msg = yield coro.receive()
            assert msg == 'ready'
            cleanup_rcoros.add(rcoro) # this will be cleaned up at the end
            if status['submitted'] < njobs:
                rcoro = yield computation.run_at(rcoro.location, compute_proc, random.uniform(1, 5))
                if isinstance(rcoro, asyncoro.Coro):
                    status['submitted'] += 1
        else:
            print('Setup of %s failed' % where)

    computation.status_coro = coro
    if (yield computation.schedule()):
        raise Exception('Failed to schedule computation')
    while True:
        msg = yield coro.receive()
        if isinstance(msg, asyncoro.MonitorException):
            # a process finished job
            rcoro = msg.args[0]
            if msg.args[1][0] == StopIteration:
                result = msg.args[1][1]
                print('%s: %s computed: %s' % (status['done'], rcoro.location, result))
            else:
                asyncoro.logger.warning('%s terminated with "%s"' %
                                        (rcoro.location, str(msg.args[1])))
            status['done'] += 1
            if status['done'] == njobs:
                break
            if status['submitted'] < njobs:
                # schedule another job at this process
                rcoro = yield computation.run_at(rcoro.location, compute_proc, random.uniform(1, 5))
                if isinstance(rcoro, asyncoro.Coro):
                    status['submitted'] += 1
        elif isinstance(msg, DiscoroStatus):
            # asyncoro.logger.debug('Node/Server status: %s, %s' % (msg.status, msg.info))
            if msg.status == discoro.Scheduler.ServerInitialized and status['submitted'] < njobs:
                # a new process is available; initialize it
                asyncoro.Coro(init_proc, msg.info)
        else:
            asyncoro.logger.debug('Ignoring status message %s' % str(msg))

    # cleanup processes
    for rcoro in cleanup_rcoros:
        if (yield rcoro.deliver('cleanup', timeout=5)) != 1:
            asyncoro.logger.warning('cleanup failed for %s' % rcoro)
    yield computation.close()


if __name__ == '__main__':
    import logging, random, sys
    asyncoro.logger.setLevel(logging.DEBUG)
    # if scheduler is not already running (on a node as a program),
    # start it (private scheduler):
    discoro.Scheduler()
    computation = discoro.Computation([compute_proc])
    # run 10 jobs
    asyncoro.Coro(client_proc, computation, 10).value()
