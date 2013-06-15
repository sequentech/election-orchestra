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

import logging
import os

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from frestq import decorators
from frestq.app import app, run_app, db

logging.basicConfig(level=logging.DEBUG)

### configuration

# debug, set to false on production deployment
DEBUG = True

# URL to our HTTP server
VERIFICATUM_SERVER_URL = 'http://127.0.0.1'

VERIFICATUM_SERVER_PORT_RANGE = [4081, 4083]

# Socket address given as <hostname>:<port> to our hint server.
# A hint server is a simple UDP server that reduces latency and
# traffic on the HTTP servers.
VERIFICATUM_HINT_SERVER_SOCKET = '127.0.0.1'

VERIFICATUM_HINT_SERVER_PORT_RANGE = [8081, 8083]

ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db.sqlite' % ROOT_PATH

PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/private')
PUBLIC_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/public')

PUBLIC_DATA_URL = 'http://127.0.0.1:8082/'

import models
import director_jobs
import performer_jobs

from public_api import public_api
app.register_blueprint(public_api, url_prefix='/public_api')

if __name__ == "__main__":
    run_app(config_object=__name__)
