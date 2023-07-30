#!/bin/bash

set -eux -o  pipefail

echo "entrypoint: state of the vars before assuming defaults:"
export

# Set some default values
LOG_LEVEL="${LOG_LEVEL:-debug}"
FLASK_APP="${FLASK_APP:-election_orchestra.app:app}"
EO_FLASK_RUN_HOST="${EO_FLASK_RUN_HOST:-0.0.0.0}"
EO_FLASK_RUN_PORT="${EO_FLASK_RUN_PORT:-8081}"
VFORK_RANDOM_SOURCE="${VFORK_RANDOM_SOURCE:-/datastore/mixnet_random_source}"
VFORK_RANDOM_SEED="${VFORK_RANDOM_SEED:-/mixnet_random_seed}"
RANDOM_DEVICE="${RANDOM_DEVICE:-/dev/urandom}"
TRUSTEES="${TRUSTEES:-trustee1,trustee2}"
ETCD_ENDPOINT="${ETCD_ENDPOINT:-}"
SERVICE_NAME="${SERVICE_NAME:-trustee1}"

echo "entrypoint: state of the vars after assuming defaults:"
export

run_cmd() {
    set +e  # Temporarily disable the 'errexit' option
    [ -f exit_status.txt ] && rm -f exit_status.txt
    touch exit_status.txt 
    export run_stdout=$($1; echo $? > exit_status.txt)
    export run_exit_status=$(cat exit_status.txt)
    [ -f exit_status.txt ] && rm -f exit_status.txt
    set -e  # Re-enable the 'errexit' option
}

# Ensure we have our own TLS certificates
create-cert.sh

# we will now upload our certificate and update the other trustees certificates
# but only if $ETCD_ENDPOINT var is set
if [[ ! -z "${ETCD_ENDPOINT}" ]]; then
    # Upload our eopeer package to etcd
    EO_PACKAGE="$(eopeers --show-mine)"
    etcdctl --endpoints="${ETCD_ENDPOINT}" put "/${SERVICE_NAME}/eopackage" "${EO_PACKAGE}"


    IFS=',' read -ra trustees_array <<< "$TRUSTEES"

    # Iterate over the array, wait to get their package; and update it if it's different
    for trustee in "${trustees_array[@]}"; do
        # skip ourselves
        if [[ "$SERVICE_NAME" == "$trustee" ]]; then
            continue
        fi

        # obtain the peer package from etcd
        NEW_EO_PACKAGE=""
        while [[ -z "${NEW_EO_PACKAGE}" ]]; do
            echo "eopeers: obtaining $trustee package.."
            NEW_EO_PACKAGE="$(etcdctl --endpoints=${ETCD_ENDPOINT} get --print-value-only "/${trustee}/eopackage")"
            sleep 2
        done
        echo "eopeers: obtained the peer package for $trustee"
        run_cmd "eopeers --show ${trustee}"
        OLD_EO_PACKAGE="$run_stdout"
        
        # the package was installed but it changed, so updated it
        if [[ "$run_exit_status" == "0" && "${OLD_EO_PACKAGE}" != "${NEW_EO_PACKAGE}" ]]; then
            echo "eopeers: the $trustee package was installed but it changed, so reinstalling it.."
            eopeers --uninstall "${trustee}"
            echo "${NEW_EO_PACKAGE}" > "${trustee}-tmp.pkg"
            eopeers --install "${trustee}-tmp.pkg"
        elif [[ "$run_exit_status" != "0" ]]; then
            echo "eopeers: the $trustee package was not installed, so installing it.."
            echo "${NEW_EO_PACKAGE}" > "${trustee}-tmp.pkg"
            eopeers --install "${trustee}-tmp.pkg"
        fi
    done
fi

# Ensure mixnet randomness is initialized
echo "mixnet: checking '${VFORK_RANDOM_SOURCE}'.."
if [ ! -f "${VFORK_RANDOM_SOURCE}" ]; then
    echo "mixnet: '${VFORK_RANDOM_SOURCE}' not found, initializing it.."
    vog -rndinit RandomDevice "${RANDOM_DEVICE}"
else
    echo "mixnet: '${VFORK_RANDOM_SOURCE}' found"
fi

# Ensure that the DB tables are created
echo "election-orchestra: ensuring DB tables are in place.."
python -m election_orchestra.app --createdb
echo "election-orchestra: database tables created"

echo "election-orchestra: launching gunicorn service.."

# Launch the election-orchestra service
gunicorn \
    -b "${EO_FLASK_RUN_HOST}:${EO_FLASK_RUN_PORT}" \
    --log-level "${LOG_LEVEL}" \
    "${FLASK_APP}"

