#!/usr/bin/env python3

#
# SPDX-FileCopyrightText: 2013-2021 Agora Voting SL <contact@nvotes.com>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import sys
import hashlib
from functools import partial
from base64 import urlsafe_b64encode

BUF_SIZE = 10*1024

def hash_data(data):
    '''
    Return the hexdigest of the data
    '''
    hash = hashlib.sha256()
    hash.update(data.encode('utf-8'))
    return urlsafe_b64encode(hash.digest()).decode('utf-8')

def hash_file(file_path):
    '''
    Returns the hexdigest of the hash of the contents of a file, given the file
    path.

    Same as executing:
    openssl sha256 -binary <file_path> | openssl base64
    '''
    hash = hashlib.sha256()
    f = open(file_path, 'rb')
    for chunk in iter(partial(f.read, BUF_SIZE), b''):
        hash.update(chunk)
    f.close()
    return urlsafe_b64encode(hash.digest()).decode('utf-8')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: %s <file-path> to obtain the sha256sum" % sys.argv[0])
        exit(1)

    print("sha256 hash of " + sys.argv[1] + " = " + hash_file(sys.argv[1]))