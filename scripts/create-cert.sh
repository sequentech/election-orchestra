#!/bin/bash

set -eux -o  pipefail

CERT_COUNTRY="${CERT_COUNTRY:-EN}"
CERT_STATE="${CERT_STATE:-New York}"
LOCALITY="${LOCALITY:-New York}"
ORG="${ORG:-Example}"
ORG_UNIT="${ORG_UNIT:-Example}"
HOST="${HOST:-some-hostname}"
COMMON_NAME="${COMMON_NAME:-some-hostname}"
EMAIL="${EMAIL-info@example.com}"
DNS1="${DNS1:-dns1}"
KEY_LENGTH="${KEY_LENGTH:-4096}"
KEY_ALGORITHM="${KEY_ALGORITHM:-rsa}"

CERT_DIR="${CERT_DIR:-/datastore/certs/}"
CERT_PATH="${CERT_PATH:-$CERT_DIR/cert.pem}"
CERT_KEY_PATH="${CERT_KEY_PATH:-$CERT_DIR/key-nopass.pem}"
CERT_CALIST_PATH="${CERT_CALIST_PATH:-$CERT_DIR/calist}"
CERT_DAYS="${CERT_DAYS:-3650}"
CERT_DIGEST="${CERT_DIGEST:-sha256}"

CREATE_CERT=${CREATE_CERT:-true}
CALIST_COPY=""

if [ ! -f "${CERT_PATH}" ]; then
  CREATE_CERT=true
  if [ ! -d "${CERT_DIR}" ]; then
    mkdir -p "${CERT_DIR}"
  fi
fi

if [ true == "$CREATE_CERT" ]; then
  openssl req \
    -nodes \
    -x509 \
    -newkey "${KEY_ALGORITHM}:${KEY_LENGTH}" \
    -extensions v3_ca \
    -keyout "${CERT_KEY_PATH}" \
    -out "${CERT_PATH}" \
    -days "${CERT_DAYS}" \
    -subj "/C=${CERT_COUNTRY}/ST=${CERT_STATE}/L=${LOCALITY}/O=${ORG}/OU=${ORG_UNIT}/CN=${COMMON_NAME}/emailAddress=${EMAIL}" \
    -config <(cat <<-EOF
[req]
default_bits           = ${KEY_LENGTH}
default_md             = ${CERT_DIGEST}
distinguished_name     = req_distinguished_name
x509_extensions        = v3_ca

[ req_distinguished_name ]
countryName            = ${CERT_COUNTRY}
stateOrProvinceName    = ${STATE}
localityName           = ${LOCALITY}
organizationName       = ${ORG}
organizationalUnitName = ${ORG_UNIT}
commonName             = ${COMMON_NAME}
emailAddress           = ${EMAIL}

[ v3_ca ]
# The extentions to add to a self-signed cert
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer:always
basicConstraints       = CA:TRUE
keyUsage               = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment, keyAgreement, keyCertSign
subjectAltName         = DNS:${DNS1},DNS:${COMMON_NAME}
issuerAltName          = issuer:copy

EOF
)
  cp "$CERT_PATH" "$CERT_CALIST_PATH"
  echo "$CALIST_COPY" >> "$CERT_CALIST_PATH"
fi
