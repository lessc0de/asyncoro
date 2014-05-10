# Asynchronous pipe example with "communicate" method that is similar
# to Popen's "communicate". Same example is used to show how custom
# write/read processes can be provided to feed / read from the
# asynchronous pipe

# argv[1] must be a text file

import sys, os, logging, traceback, subprocess

if sys.version_info.major > 2:
    import asyncoro3 as asyncoro
    import asyncfile3 as asyncfile
else:
    import asyncoro
    import asyncfile
    
def communicate(input, coro=None):
    popen = subprocess.Popen(['sha1sum'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    # convert pipe to asynchronous version
    apipe = asyncfile.AsyncPipe(popen)
    # 'communicate' takes either the data or file descriptor with data
    # (if file is too large to read in full) as input
    input = open(input)
    stdout, stderr = yield apipe.communicate(input)
    print('communicate sha1sum: %s' % stdout)

def custom_feeder(input, coro=None):
    def write_proc(fin, pipe, coro=None):
        while True:
            data = yield os.read(fin.fileno(), 8*1024)
            if not data:
                break
            n = yield pipe.write(data, full=True)
            assert n == len(data)
        fin.close()
        pipe.stdin.close()

    def read_proc(pipe, coro=None):
        # output from sha1sum is small, so read until EOF
        data = yield pipe.stdout.read()
        pipe.stdout.close()
        raise StopIteration(data)

    popen = subprocess.Popen(['sha1sum'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    apipe = asyncfile.AsyncPipe(popen)
    reader = asyncoro.Coro(read_proc, apipe)
    writer = asyncoro.Coro(write_proc, open(input), apipe)
    stdout = yield reader.finish()
    print('     feeder sha1sum: %s' % stdout)

# asyncoro.logger.setLevel(logging.DEBUG)

# simpler version using 'communicate'
coro = asyncoro.Coro(communicate, sys.argv[1])
coro.value() # wait for it to finish

# alternate version with custom read and write processes
asyncoro.Coro(custom_feeder, sys.argv[1])
