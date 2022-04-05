# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
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
    'mixnet_queue': {
        'max_threads': 1,
    }
}