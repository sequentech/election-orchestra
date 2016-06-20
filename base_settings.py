# This file is part of election-orchestra.
# Copyright (C) 2013-2016  Agora Voting SL <agora@agoravoting.com>

# election-orchestra is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License.

# election-orchestra  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with election-orchestra.  If not, see <http://www.gnu.org/licenses/>.

# debug, set to false on production deployment
DEBUG = True

ROOT_URL = 'https://127.0.0.1:5000/api/queues'

# URL to our HTTP server
VFORK_SERVER_URL = 'http://127.0.0.1'

VFORK_SERVER_PORT_RANGE = [4081, 4083]

# Socket address given as <hostname>:<port> to our hint server.
# A hint server is a simple UDP server that reduces latency and
# traffic on the HTTP servers.
VFORK_HINT_SERVER_SOCKET = '127.0.0.1'

VFORK_HINT_SERVER_PORT_RANGE = [8081, 8083]

import os
ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db.sqlite' % ROOT_PATH

PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/private')
PUBLIC_DATA_PATH = '/srv/election-orchestra/server1/public'
PUBLIC_DATA_BASE_URL = 'https://127.0.0.1:5000/public_data'

# security configuration
SSL_CERT_PATH = '%s/certs/selfsigned/cert.pem' % ROOT_PATH
SSL_KEY_PATH = '%s/certs/selfsigned/key-nopass.pem' % ROOT_PATH
ALLOW_ONLY_SSL_CONNECTIONS = True

AUTOACCEPT_REQUESTS = True

MAX_NUM_QUESTIONS_PER_ELECTION = 40

KILL_ALL_VFORK_BEFORE_START_NEW = False

QUEUES_OPTIONS = {
    'launch_task': {
        'max_threads': 1
    },
    'vfork_queue': {
        'max_threads': 1,
    }
}