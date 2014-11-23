# debug, set to false on production deployment
DEBUG = True

ROOT_URL = 'https://127.0.0.1:5000/api/queues'

# URL to our HTTP server
VERIFICATUM_SERVER_URL = 'http://127.0.0.1'

VERIFICATUM_SERVER_PORT_RANGE = [4081, 4083]

# Socket address given as <hostname>:<port> to our hint server.
# A hint server is a simple UDP server that reduces latency and
# traffic on the HTTP servers.
VERIFICATUM_HINT_SERVER_SOCKET = '127.0.0.1'

VERIFICATUM_HINT_SERVER_PORT_RANGE = [8081, 8083]

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

KILL_ALL_VERIFICATUM_BEFORE_START_NEW = False

QUEUES_OPTIONS = {
    'launch_task': {
        'max_threads': 1
    },
    'verificatum_queue': {
        'max_threads': 1,
    }
}