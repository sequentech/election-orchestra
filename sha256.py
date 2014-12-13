#!/usr/bin/env python

# -*- coding: utf-8 -*-

# This file is part of election-orchestra.
# Copyright (C) 2013  Eduardo Robles Elvira <edulix AT wadobo DOT com>

# election-orchestra is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License.

# election-orchestra  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with election-orchestra.  If not, see <http://www.gnu.org/licenses/>.

import sys
import hashlib
from functools import partial
from base64 import urlsafe_b64encode

BUF_SIZE = 10*1024

def hash_file(file_path):
    '''
    Returns the hexdigest of the hash of the contents of a file, given the file
    path.

    Same as executing:
    openssl sha256 -binary <file_path> | openssl base64
    '''
    hash = hashlib.sha256()
    f = open(file_path, 'r')
    for chunk in iter(partial(f.read, BUF_SIZE), b''):
        hash.update(chunk)
    f.close()
    return urlsafe_b64encode(hash.digest())

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: %s <file-path> to obtain the sha256sum" % sys.argv[0])
        exit(1)

    print("sha256 hash of " + sys.argv[1] + " = " + hash_file(sys.argv[1]))