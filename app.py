#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This file is part of election-orchestra.
# Copyright (C) 2013-2020  Agora Voting SL <contact@nvotes.com>

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
import sys

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Note: we need to import app before decorators or it won't work
from frestq.app import app
from frestq import decorators

logging.basicConfig(level=logging.DEBUG)

### configuration

# debug, set to false on production deployment
DEBUG = True

# URL to our HTTP server
VFORK_SERVER_URL = 'http://127.0.0.1'

VFORK_SERVER_PORT_RANGE = [4081, 4083]

# Socket address given as <hostname>:<port> to our hint server.
# A hint server is a simple UDP server that reduces latency and
# traffic on the HTTP servers.
VFORK_HINT_SERVER_SOCKET = '127.0.0.1'

VFORK_HINT_SERVER_PORT_RANGE = [8081, 8083]

ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db.sqlite' % ROOT_PATH

PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/private')
PUBLIC_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/public')

import models
import reject_adapter
import create_election.director_jobs
import create_election.performer_jobs
import tally_election.director_jobs
import tally_election.performer_jobs
from public_api import public_api
from taskqueue import start_queue


def extra_parse_args(self, parser):
    parser.add_argument("--reset-tally", help="Enable making a second tally for :election_id",
                        type=int)

def extra_run(self):
    if self.pargs.reset_tally and isinstance(self.pargs.reset_tally,(int,long)):
        election_id = self.pargs.reset_tally
        tally_election.performer_jobs.reset_tally(election_id)
        return True

    return False

if __name__ == "__main__":
    app.configure_app(scheduler=False, config_object=__name__)
    app.register_blueprint(public_api, url_prefix='/public_api')
    if len(sys.argv) == 3 and sys.argv[1] == "create-tarball":
        from tools import create_tarball
        create_tarball.create(sys.argv[2])
        exit(0)
    app.run(parse_args=True, extra_parse_func=extra_parse_args, 
            extra_run=extra_run)
else:
    app.configure_app(config_object=__name__)
    app.register_blueprint(public_api, url_prefix='/public_api')
    start_queue()

