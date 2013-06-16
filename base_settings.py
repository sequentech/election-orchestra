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

import os
ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]

SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db.sqlite' % ROOT_PATH

PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/private')
PUBLIC_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/public')

PUBLIC_DATA_URL = 'http://127.0.0.1:8082/'
