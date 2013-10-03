# -*- coding: utf-8 -*-

# This file is part of election-orchestra.
# Copyright (C) 2013  Eduardo Robles Elvira <edulix AT wadobo DOT com>

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

from models import Election, Authority
from utils import *

BUF_SIZE = 10*1024

def hash_file(file_path):
    '''
    Returns the hexdigest of the hash of the contents of a file, given the file
    path.
    '''
    hash = hashlib.sha512()
    f = open(file_path, 'r')
    for chunk in f.read(BUF_SIZE):
        hash.update(chunk)
    f.close()
    return hash.hexdigest()

@decorators.task(action="review_tally", queue="orchestra_performer")
def review_tally(task):
    '''
    Generates the local private info for a new election
    '''
    data = task.get_data()['input_data']

    # check input data
    requirements = [
        {'name': u'session_id', 'isinstance': basestring},
        {'name': u'callback_url', 'isinstance': basestring},
        {'name': u'votes_url', 'isinstance': basestring},
        {'name': u'votes_hash', 'isinstance': basestring},
        {'name': u'extra', 'isinstance': list},
    ]

    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
                req['isinstance']):
            print req['name'], data.get(req['name'], None), type(data[req['name']])
            raise TaskError(dict(reason="invalid %s parameter" % req['name']))


    if not re.match("^[a-zA-Z0-9_-]+$", data['session_id']):
        raise TaskError(dict(reason="invalid characters in session id"))

    if not data['votes_hash'].startswith("sha512://"):
        raise TaskError(dict(reason="invalid votes_hash, must be sha512"))

    # check election has been created successfully
    session_id = data['session_id']

    election = db.session.query(Election)\
        .filter(Election.session_id == session_id).first()
    if not election:
        raise TaskError(dict(reason="election not created"))

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)

    protinfo_path = os.path.join(election_private_path, 'protInfo.xml')
    pubkey_path = os.path.join(election_private_path, 'publicKey_raw')
    if not os.path.exists(protinfo_path) or not os.path.exists(pubkey_path):
        raise TaskError(dict(reason="election not created"))

    # if there have been previous tally, remove
    ciphertexts_path = os.path.join(election_private_path, 'ciphertexts_native')
    prev_tallies = False
    if os.path.exists(ciphertexts_path):
        prev_tallies = True
        os.unlink(ciphertexts_path)

    # reset securely
    subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml", "-f"],
        cwd=election_private_path)

    # if there were previous tallies, remove the tally approved flag file
    approve_path = os.path.join(private_data_path, session_id, 'tally_approved')
    if os.path.exists(approve_path):
        os.unlink(approve_path)

    # retrieve votes/ciphertexts
    callback_url = data['votes_url']
    r = requests.get(data['votes_url'], verify=False, stream=True)
    if r.status_code != 200:
        raise TaskError(dict(reason="error downloading the votes"))

    # write ciphertexts to disk
    ciphertexts_file = open(ciphertexts_path, 'w')
    for chunk in r.iter_content(10*1024):
        ciphertexts_file.write(chunk)
    ciphertexts_file.close()

    # check votes hash
    input_hash = data['votes_hash'].replace('sha512://', '')
    if input_hash != hash_file(ciphertexts_path):
        raise TaskError(dict(reason="invalid votes_hash"))

    # transform ciphertexts into native
    subprocess.check_call(["vmnc", "-ciphs", "-ini", "native", "ciphertexts_native",
        "ciphertexts_raw"], cwd=election_private_path)

    # request user to decide
    label = "approve_election"
    info_text = """* URL: %(url)s
* Title: %(title)s
* Description: %(description)s
* Voting period: %(start_date)s - %(end_date)s
* Previous tallies: %(prev_tallies)s
* Authorities: %(authorities)s""" % dict(
        url = election.url,
        title = election.title,
        prev_tallies = repr(prev_tallies),
        description = election.description,
        start_date = election.voting_start_date.isoformat(),
        end_date = election.voting_end_date.isoformat(),
        authorities = dumps([auth.to_dict() for auth in election.authorities], indent=4)
    )
    approve_task = ExternalTask(label=label,
        data=info_text)
    check_approval_task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="check_tally_approval",
        queue="orchestra_performer",
        data=dict(session_id=session_id))
    task.add(approve_task)
    task.add(check_approval_task)

@decorators.task(action="check_tally_approval", queue="orchestra_performer")
@decorators.local_task
def check_tally_approval(task):
    '''
    Check if the tally was a approved. If it was, mark the tally as approved.
    If it was not, raise an exception so that the director gets the bad notice.
    '''
    if task.get_prev().get_data()['output_data'] != dict(status="accepted"):
        task.set_output_data("task not accepted")
        raise TaskError(dict(reason="task not accepted"))

    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    approve_path = os.path.join(private_data_path, session_id, 'tally_approved')

    # create the tally_approved flag file
    open(approve_path, 'a').close()


@decorators.task(action="perform_tally", queue="verificatum_queue")
class PerformTallyTask(TaskHandler):
    def execute(self):
        '''
        Performs the tally in a synchronized way with the other authorities
        '''
        input_data = self.task.get_data()['input_data']
        session_id = input_data['session_id']

        private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
        election_private_path = os.path.join(private_data_path, session_id)
        tally_approved_path = os.path.join(election_private_path, 'tally_approved')

        # check that we have approved the tally
        if not os.path.exists(tally_approved_path):
            raise TaskError(dict(reason="task not accepted"))

        os.unlink(tally_approved_path)

        protinfo_path = os.path.join(election_private_path, 'protInfo.xml')
        if not os.path.exists(protinfo_path):
            protinfo_file = codecs.open(protinfo_path, 'w', encoding='utf-8')
            protinfo_file.write(input_data['protInfo_content'])
            protinfo_file.close()

        subprocess.check_call(["vmn", "-mix", "privInfo.xml", "protInfo.xml",
            "ciphertexts_raw", "plaintexts_raw"], cwd=election_private_path)

    def handle_error(self, error):
        '''
        If there's any error, remove the tally_approved flag
        '''
        session_id = self.task.get_data()['input_data'].get('session_id', '')
        if not session_id:
            return

        private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
        election_private_path = os.path.join(private_data_path, session_id)
        approve_path = os.path.join(private_data_path, session_id, 'tally_approved')
        if os.path.exists(approve_path):
            os.unlink(approve_path)

        # reset securely
        subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml", "-f"],
            cwd=election_private_path)


@decorators.task(action="verify_and_publish_tally", queue="orchestra_performer")
def verify_and_publish_tally(task):
    '''
    Once a tally has been performed, verify the result and if it's ok publish it
    '''
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)
    plaintexts_raw_path = os.path.join(election_private_path, 'plaintexts_raw')
    plaintexts_native_path = os.path.join(election_private_path, 'plaintexts_native')
    proofs_path = os.path.join(election_private_path, 'dir', 'roProof')
    protinfo_path = os.path.join(election_private_path, 'protInfo.xml')

    # check that we have a tally
    if not os.path.exists(proofs_path) or not os.path.exists(plaintexts_raw_path):
        raise TaskError(dict(reason="proofs or plaintexts couldn't be verified"))

    # remove any previous plaintexts_native
    if os.path.exists(plaintexts_native_path):
        os.unlink(plaintexts_native_path)

    # transform plaintexts into native format
    subprocess.check_call(["vmnc", "-plain", "-outi", "native", "plaintexts_raw",
                           "plaintexts_native"], cwd=election_private_path)

    # verify the proofs. sometimes verificatum raises an exception at the end
    # so we dismiss it if the verification is successful. TODO: fix that in
    # verificatum
    try:
        output = subprocess.check_output(["vmnv", protinfo_path, proofs_path, "-v"])
    except subprocess.CalledProcessError, e:
        output = e.output
    if "Verification completed SUCCESSFULLY after" not in output:
        raise TaskError(dict(reason="invalid tally proofs"))

    # remove any previously published tally or plaintext files
    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, session_id)
    if not os.path.exists(election_pubpath):
        mkdir_recursive(election_pubpath)

    tally_path = os.path.join(election_pubpath, 'tally.tar.gz')
    plaintexts_path2 = os.path.join(election_pubpath, 'plaintexts_native')
    if os.path.exists(tally_path):
        os.unlink(tally_path)
    if os.path.exists(plaintexts_path2):
        os.unlink(plaintexts_path2)

    # publish plaintexts
    shutil.copy(plaintexts_native_path, plaintexts_path2)

    # once the proofs have been verified, create and publish a tarball
    # containing plaintexts, protInfo and proofs
    tar = tarfile.open(tally_path, 'w')
    tar.add(plaintexts_native_path, arcname="plaintexts_native")
    tar.add(proofs_path, arcname="proofs")
    tar.add(protinfo_path, "protInfo.xml")
    tar.close()

    # and publish also the sha512 of the tarball
    tally_hash_path = os.path.join(pubdata_path, session_id, 'tally.tar.gz.sha512')
    tally_hash_file = open(tally_hash_path, 'w')
    tally_hash_file.write(hash_file(tally_path))
    tally_hash_file.close()