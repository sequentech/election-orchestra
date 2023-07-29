#!/bin/bash

set -eux -o  pipefail

LOG_LEVEL="${LOG_LEVEL:-debug}"
FLASK_APP="${FLASK_APP:-election_orchestra.app:app}"
FLASK_RUN_HOST="${FLASK_RUN_HOST:-0.0.0.0}"
VFORK_RANDOM_SOURCE="${VFORK_RANDOM_SOURCE:-/datastore/mixnet_random_source}"
VFORK_RANDOM_SEED="${VFORK_RANDOM_SEED:-/mixnet_random_seed}"
RANDOM_DEVICE="${RANDOM_DEVICE:-/dev/urandom}"

create-cert.sh

echo "mixnet: checking '${VFORK_RANDOM_SOURCE}'.."
if [ ! -f "${VFORK_RANDOM_SOURCE}" ]; then
    echo "mixnet: '${VFORK_RANDOM_SOURCE}' not found, initializing it.."
    vog -rndinit RandomDevice "${RANDOM_DEVICE}"
else
    echo "mixnet: '${VFORK_RANDOM_SOURCE}' found"
fi

echo "election-orchestra: ensuring DB tables are in place.."
python -m election_orchestra.app --createdb
echo "election-orchestra: database tables created"

echo "election-orchestra: launching gunicorn service.."

gunicorn \
    -b "${FLASK_RUN_HOST}:${FLASK_RUN_PORT}" \
    --log-level "${LOG_LEVEL}" \
    "${FLASK_APP}"

