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

import os
import subprocess

from frestq.app import app

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
                os.mkdir(p, 0755)

def get_server_url():
    '''
    Return a server url that can be used
    '''
    return app.config.get('VERIFICATUM_SERVER_URL', '') +\
        str(app.config.get('VERIFICATUM_SERVER_PORT_RANGE', '')[0])


def get_hint_server_url():
    '''
    Return a hint server url that can be used
    '''
    return app.config.get('VERIFICATUM_HINT_SERVER_URL', '') +\
        str(app.config.get('VERIFICATUM_HINT_SERVER_PORT_RANGE', '')[0])
