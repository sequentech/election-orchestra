#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of election-orchestra.
# Copyright (C) 2013  Agora Voting SL <agora@agoravoting.com>

# election-orchestra is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License.

# election-orchestra  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with election-orchestra.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import tarfile
import codecs
import hashlib
import subprocess
import json
import requests
import shutil
from datetime import datetime

from frestq.app import app, db
from frestq import decorators
from frestq.utils import dumps, loads
from frestq.tasks import SimpleTask, ParallelTask, ExternalTask, TaskError
from frestq.protocol import certs_differ
from frestq.action_handlers import TaskHandler

from models import Election, Authority, Session
from utils import *
from vmn import *


BUF_SIZE = 10*1024

# we just use always the same timestamp for the files for creating
# deterministic tars
MAGIC_TIMESTAMP = 1394060400

def hash_file(file_path):
    '''
    Returns the hexdigest of the hash of the contents of a file, given the file
    path.
    '''
    hash = hashlib.sha256()
    f = open(file_path, 'r')
    for chunk in f.read(BUF_SIZE):
        hash.update(chunk)
    f.close()
    return hash.hexdigest()

def verify_pok_plaintext(pk, proof, ciphertext):
    '''
    verifies the proof of knowledge of the plaintext, given encrypted data and
    the public key

    "pk" must be a dictonary with keys "g", "p", and values must be integers.

    More info:
    http://courses.csail.mit.edu/6.897/spring04/L19.pdf - 2.1 Proving
    Knowledge of Plaintext
    '''
    pk_p = pk['p']
    pk_g = pk['g']
    commitment = int(proof['commitment'])
    response = int(proof['response'])
    challenge =  int(proof['challenge'])
    alpha = int(ciphertext['alpha'])

    # verify the challenge is valid
    hash = hashlib.sha256()
    hash.update(("%d/%d" % (alpha, commitment)).encode('utf-8'))
    challenge_calculated = int(hash.hexdigest(), 16)
    assert challenge_calculated == challenge

    first_part = pow(pk_g, response, pk_p)
    second_part = (commitment * pow(alpha, challenge, pk_p)) % pk_p

    # check g^response == commitment * (g^t) ^ challenge == commitment * (alpha) ^ challenge
    assert first_part == second_part

def create(election_id):
    '''
    create the tarball
    '''
    if not re.match("^[a-zA-Z0-9_-]+$", election_id):
        raise TaskError(dict(reason="invalid characters in election_id"))

    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if not election:
        raise TaskError(dict(reason="election not found"))

    privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(privdata_path, election_id)

    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, election_id)
    tally_path = os.path.join(election_pubpath, 'tally.tar.gz')
    tally_hash_path = os.path.join(election_pubpath, 'tally.tar.gz.sha256')

    # check election_pubpath already exists - it should contain pubkey etc
    if not os.path.exists(election_pubpath):
        raise TaskError(dict(reason="election public path doesn't exist"))

    # check no tally exists yet
    if os.path.exists(tally_path):
        raise TaskError(dict(reason="tally already exists, "
                             "election_id = %s" % election_id))

    pubkeys = []
    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        plaintexts_raw_path = os.path.join(session_privpath, 'plaintexts_raw')
        plaintexts_json_path = os.path.join(session_privpath, 'plaintexts_json')
        proofs_path = os.path.join(session_privpath, 'dir', 'roProof')
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')

        pubkey_path = os.path.join(privdata_path, election_id, session.id, 'publicKey_json')
        with open(pubkey_path, 'r') as pubkey_file:
            pubkeys.append(json.loads(pubkey_file.read()))
            pubkey_file.close()

        # check that we have a tally
        if not os.path.exists(proofs_path) or not os.path.exists(plaintexts_raw_path):
            raise TaskError(dict(reason="proofs or plaintexts couldn't be verified"))

        # remove any previous plaintexts_json
        if os.path.exists(plaintexts_json_path):
            os.unlink(plaintexts_json_path)

        # transform plaintexts into json format
        #call_cmd(["vmnc", "-plain", "-outi", "json", "plaintexts_raw",
        #          "plaintexts_json"], cwd=session_privpath, check_ret=0,
        #          timeout=3600)
        v_convert_plaintexts_json(session_privpath)

    # get number of invalid votes that were detected before decryption
    invalid_votes_path = os.path.join(election_privpath, 'invalid_votes')
    invalid_votes = int(open(invalid_votes_path, 'r').read(), 10)

    result_privpath = os.path.join(election_privpath, 'result_json')

    # create and publish a tarball
    # containing plaintexts, protInfo and proofs
    # NOTE: we try our best to do a deterministic tally, i.e. one that can be
    # generated exactly the same bit by bit by all authorities

    # For example, here we open tarfile setting cwd so that the header of the
    # tarfile doesn't contain the full path, which would make the tally.tar.gz
    # not deterministic as it might vary from authority to authority
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(tally_path))
        import time
        old_time = time.time
        time.time = lambda: MAGIC_TIMESTAMP
        tar = tarfile.open(os.path.basename(tally_path), 'w|gz')
    finally:
        time.time = old_time
        os.chdir(cwd)
    timestamp = MAGIC_TIMESTAMP

    ciphertexts_path = os.path.join(election_privpath, 'ciphertexts_json')
    pubkeys_path = os.path.join(privdata_path, election_id, 'pubkeys_json')

    with open(pubkeys_path, mode='w') as pubkeys_f:
        pubkeys_f.write(json.dumps(pubkeys,
            ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': ')))

    deterministic_tar_add(tar, ciphertexts_path, 'ciphertexts_json', timestamp)
    deterministic_tar_add(tar, pubkeys_path, 'pubkeys_json', timestamp)

    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        plaintexts_json_path = os.path.join(session_privpath, 'plaintexts_json')
        proofs_path = os.path.join(session_privpath, 'dir', 'roProof')
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')

        deterministic_tar_add(tar, plaintexts_json_path,
            os.path.join(session.id, 'plaintexts_json'), timestamp)
        deterministic_tar_add(tar, proofs_path,
            os.path.join(session.id, "proofs"), timestamp)
        deterministic_tar_add(tar, protinfo_path,
            os.path.join(session.id, "protInfo.xml"), timestamp)
    tar.close()

    # and publish also the sha256 of the tarball
    tally_hash_file = open(tally_hash_path, 'w')
    tally_hash_file.write(hash_file(tally_path))
    tally_hash_file.close()
    print("tally = %s" % tally_path)

def deterministic_tarinfo(tfile, filepath, arcname, timestamp, uid=1000, gid=100):
    '''
    Creates a tarinfo with some fixed data
    '''
    tarinfo = tfile.gettarinfo(filepath, arcname)
    tarinfo.uid = uid
    tarinfo.gid = gid
    tarinfo.mode = 0o755 if tarinfo.isdir() else 0o644
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = timestamp
    return tarinfo

def deterministic_tar_add(tfile, filepath, arcname, timestamp, uid=1000, gid=100):
    '''
    tries its best to do a deterministic add of the file
    '''
    tinfo = deterministic_tarinfo(tfile, filepath, arcname, timestamp,
        uid, gid)
    if tinfo.isreg():
         with open(filepath, "rb") as f:
            tfile.addfile(tinfo, f)
    else:
        tfile.addfile(tinfo)

    if os.path.isdir(filepath):
        l = os.listdir(filepath)
        l.sort() # sort or it won't be deterministic!
        for subitem in l:
            newpath = os.path.join(filepath, subitem)
            newarcname = os.path.join(arcname, subitem)
            deterministic_tar_add(tfile, newpath, newarcname, timestamp, uid,
                gid)