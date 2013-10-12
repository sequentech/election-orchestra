#!/bin/bash

cwd=$(pwd)
cd $1
vmnd -i json protInfo.xml publicKey_json 100 encrypted_texts_json
cd $cwd

python sha512.py $1/encrypted_texts_json
echo 
