#!/bin/bash

set -eux -o  pipefail

CERT_COUNTRY="${CERT_COUNTRY:-EN}"
CERT_STATE="${CERT_STATE:-New York}"
CERT_LOCALITY="${CERT_LOCALITY:-New York}"
CERT_ORG="${CERT_ORG:-Example}"
CERT_ORG_UNIT="${CERT_ORG_UNIT:-Example}"
HOST="${HOST:-some-hostname}"
CERT_COMMON_NAME="${CERT_COMMON_NAME:-some-hostname}"
CERT_EMAIL="${CERT_EMAIL-info@example.com}"
CERT_DNS1="${CERT_DNS1:-dns1}"
CERT_KEY_LENGTH="${CERT_KEY_LENGTH:-4096}"
CERT_KEY_ALGORITHM="${CERT_KEY_ALGORITHM:-rsa}"

CERT_DIR="${CERT_DIR:-/datastore/certs}"
CERT_PATH="${CERT_PATH:-$CERT_DIR/cert.pem}"
CERT_KEY_PATH="${CERT_KEY_PATH:-$CERT_DIR/key-nopass.pem}"
CERT_CALIST_PATH="${CERT_CALIST_PATH:-$CERT_DIR/calist}"
CERT_DAYS="${CERT_DAYS:-3650}"
CERT_DIGEST="${CERT_DIGEST:-sha256}"

CREATE_CERT=${CREATE_CERT:-false}
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
    -newkey "${CERT_KEY_ALGORITHM}:${CERT_KEY_LENGTH}" \
    -extensions v3_ca \
    -keyout "${CERT_KEY_PATH}" \
    -out "${CERT_PATH}" \
    -days "${CERT_DAYS}" \
    -subj "/C=${CERT_COUNTRY}/ST=${CERT_STATE}/L=${CERT_LOCALITY}/O=${CERT_ORG}/OU=${CERT_ORG_UNIT}/CN=${CERT_COMMON_NAME}/emailAddress=${CERT_EMAIL}" \
    -config <(cat <<-EOF
[req]
default_bits           = ${CERT_KEY_LENGTH}
default_md             = ${CERT_DIGEST}
distinguished_name     = req_distinguished_name
x509_extensions        = v3_ca

[ req_distinguished_name ]
countryName            = ${CERT_COUNTRY}
stateOrProvinceName    = ${CERT_STATE}
localityName           = ${CERT_LOCALITY}
organizationName       = ${CERT_ORG}
organizationalUnitName = ${CERT_ORG_UNIT}
commonName             = ${CERT_COMMON_NAME}
emailAddress           = ${CERT_EMAIL}

[ v3_ca ]
# The extentions to add to a self-signed cert
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer:always
basicConstraints       = CA:TRUE
keyUsage               = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment, keyAgreement, keyCertSign
subjectAltName         = DNS:${CERT_DNS1},DNS:${CERT_COMMON_NAME}
issuerAltName          = issuer:copy

EOF
)
  cp "$CERT_PATH" "$CERT_CALIST_PATH"
  echo "$CALIST_COPY" >> "$CERT_CALIST_PATH"
fi
