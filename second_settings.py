# -*- coding: utf-8 -*-

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

# set database uri
import os
ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]
SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db2.sqlite' % ROOT_PATH

PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore2/private')
PUBLIC_DATA_PATH = '/srv/election-orchestra/server2/public'
PUBLIC_DATA_BASE_URL = 'https://127.0.0.1:5001/public_data'

SERVER_NAME = '127.0.0.1:5001'

SERVER_PORT = 5001

ROOT_URL = 'https://127.0.0.1:5001/api/queues'

VFORK_SERVER_PORT_RANGE = [4084, 4087]

VFORK_HINT_SERVER_PORT_RANGE = [8084, 8087]

# security configuration
SSL_CERT_PATH = '%s/certs/selfsigned2/cert.pem' % ROOT_PATH
SSL_KEY_PATH = '%s/certs/selfsigned2/key-nopass.pem' % ROOT_PATH
SSL_CALIST_PATH = '%s/certs/selfsigned2/calist' % ROOT_PATH
ALLOW_ONLY_SSL_CONNECTIONS = True

AUTOACCEPT_REQUESTS = True

QUEUES_OPTIONS = {
    'vfork_queue': {
        'max_threads': 1,
    }
}