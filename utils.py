# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import os
import signal
import time
import subprocess
import hashlib

from frestq.app import app
from asyncproc import Process

def mkdir_recursive(path):
    if not os.path.exists(path):
        l=[]
        p = "/"
        l = path.split("/")
        i = 1
        while i < len(l):
            p = p + l[i] + "/"
            i = i + 1
            if not os.path.exists(p):
                os.mkdir(p, 0o755)

def get_server_url():
    '''
    Return a server url that can be used
    '''
    return "%s:%d" % (app.config.get('VFORK_SERVER_URL', ''),
        app.config.get('VFORK_SERVER_PORT_RANGE', '')[0])

def get_hint_server_url():
    '''
    Return a hint server url that can be used
    '''
    return "%s:%d" % (app.config.get('VFORK_HINT_SERVER_SOCKET', ''),
        app.config.get('VFORK_HINT_SERVER_PORT_RANGE', '')[0])

def call_cmd(cmd, timeout=-1, output_filter=None, cwd=None, check_ret=None):
    '''
    Utility to call a command.
    timeout is in seconds.
    '''
    print("call_cmd: calling " + " ".join(cmd))
    p = Process(cmd, cwd=cwd, stderr=subprocess.STDOUT)
    launch_time = time.process_time()
    output = ""

    while True:
        # check to see if process has ended
        ret = p.wait(os.WNOHANG)
        # print any new output
        o = p.read().decode('utf-8')
        if len(o) > 0:
            print("output = %s" % o)

        if output_filter:
            output_filter(p, o, output)
        output += o
        time.sleep(1)

        if ret is not None:
            if check_ret is not None:
                assert check_ret == ret
            return ret, output

        if timeout > 0 and time.process_time() - launch_time > timeout:
            p.kill(signal.SIGKILL)
            if check_ret is not None:
                assert check_ret == -1
            return -1, output


def constant_time_compare(val1, val2):
    """
    Returns True if the two strings are equal, False otherwise.
    The time taken is independent of the number of characters that match.
    For the sake of simplicity, this function executes in constant time only
    when the two strings have the same length. It short-circuits when they
    have different lengths. Since Django only uses it to compare hashes of
    known expected length, this is acceptable.
    """
    if len(val1) != len(val2):
        return False
    result = 0
    for x, y in zip(val1, val2):
        result |= ord(x) ^ ord(y)
    return result == 0

def parse_json_request(request):
    '''
    Returns the request body as a parsed json object
    '''
    return json.loads(request.body.decode('utf-8'))
