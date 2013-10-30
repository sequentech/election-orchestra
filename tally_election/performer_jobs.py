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
from agora_tally import tally
from datetime import datetime

from frestq.app import app, db
from frestq import decorators
from frestq.utils import dumps, loads
from frestq.tasks import SimpleTask, ParallelTask, ExternalTask, TaskError
from frestq.protocol import certs_differ
from frestq.action_handlers import TaskHandler

from models import Election, Authority, Session
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
    sender_ssl_cert = task.get_data()['sender_ssl_cert']
    data = task.get_data()['input_data']

    # check input data
    requirements = [
        {'name': u'election_id', 'isinstance': basestring},
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


    if not re.match("^[a-zA-Z0-9_-]+$", data['election_id']):
        raise TaskError(dict(reason="invalid characters in election_id"))

    if not data['votes_hash'].startswith("sha512://"):
        raise TaskError(dict(reason="invalid votes_hash, must be sha512"))

    # check election has been created successfully
    election_id = data['election_id']

    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if not election:
        raise TaskError(dict(reason="election not created"))

    # check sender is legitimate
    found_director = False
    for auth in election.authorities.all():
        if not certs_differ(auth.ssl_cert, sender_ssl_cert):
            found_director = True
    if not found_director:
        raise TaskError(dict(reason="review tally sent by an invalid authority"))

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(private_data_path, election_id)

    tally_path = os.path.join(election_privpath, 'tally.tar.gz')

    if not election.is_recurring and os.path.exists(tally_path):
        raise TaskError(dict(reason="election already tallied"))

    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')
        pubkey_path = os.path.join(session_privpath, 'publicKey_raw')
        if not os.path.exists(protinfo_path) or not os.path.exists(pubkey_path):
            raise TaskError(dict(reason="election not created"))

        # once we have checked that we have permissions to start doing the tally,
        # we can remove the "temporal" files of any previous tally
        ciphertexts_path = os.path.join(session_privpath, 'ciphertexts_json')
        cipherraw_path = os.path.join(session_privpath, 'ciphertexts_raw')
        if os.path.exists(ciphertexts_path):
            os.unlink(ciphertexts_path)
        if os.path.exists(cipherraw_path):
            os.unlink(cipherraw_path)

        # reset securely
        subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml",
            "-f"], cwd=session_privpath)

    # if there were previous tallies, remove the tally approved flag file
    approve_path = os.path.join(private_data_path, election_id, 'tally_approved')
    if os.path.exists(approve_path):
        os.unlink(approve_path)

    # retrieve votes/ciphertexts
    callback_url = data['votes_url']
    r = requests.get(data['votes_url'], verify=False, stream=True)
    if r.status_code != 200:
        raise TaskError(dict(reason="error downloading the votes"))

    # write ciphertexts to disk
    ciphertexts_path = os.path.join(election_privpath, 'ciphertexts_json')
    ciphertexts_file = open(ciphertexts_path, 'w')
    for chunk in r.iter_content(10*1024):
        ciphertexts_file.write(chunk)
    ciphertexts_file.close()

    # check votes hash
    input_hash = data['votes_hash'].replace('sha512://', '')
    if input_hash != hash_file(ciphertexts_path):
        raise TaskError(dict(reason="invalid votes_hash"))

    # transform input votes into something readable by verificatum. Basically
    # we read each line of the votes file, which corresponds with a ballot,
    # and split each choice to each session
    # So basically each input line looks like:
    # {"choices": [vote_for_session1, vote_for_session2, [...]], "proofs": []}
    #
    # And we generate N ciphertexts_json files, each of which, for each of
    # those lines input lines, will contain a line with vote_for_session<i>.
    # NOTE: This is the inverse of what the demociphs.py script does
    invotes_file = None
    outvotes_files = []
    try:
        invotes_file = open(ciphertexts_path, 'r')
        for session in election.sessions.all():
            outvotes_path = os.path.join(election_privpath, session.id,
                'ciphertexts_json')
            outvotes_files.append(open(outvotes_path, 'w'))
        for line in invotes_file:
            line_data = json.loads(line)
            i = 0
            assert len(line_data['choices']) == len(outvotes_files)
            for choice in line_data['choices']:
                # NOTE: we use specific separators with no spaces, because
                # otherwise verificatum won't read it well
                outvotes_files[i].write(json.dumps(choice,
                    separators=(",", ":")))
                outvotes_files[i].write("\n")
                i += 1
    finally:
        if invotes_file is not None:
            invotes_file.close()
        for f in outvotes_files:
            f.close()

    # Convert each ciphertexts_json of each session into ciphertexts_raw
    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        subprocess.check_call(["vmnc", "-ciphs", "-ini", "json",
            "ciphertexts_json", "ciphertexts_raw"], cwd=session_privpath)

    autoaccept = app.config.get('AUTOACCEPT_REQUESTS', False)
    if not autoaccept:
        def str_date(date):
            if date:
                return date.isoformat()
            else:
                return ""

        # request user to decide
        label = "approve_election_tally"
        info_text = """* URL: %(url)s
* Title: %(title)s
* Description: %(description)s
 * Voting period: %(start_date)s - %(end_date)s
* Authorities: %(authorities)s""" % dict(
            url = election.url,
            title = election.title,
            description = election.description,
            start_date = str_date(election.voting_start_date),
            end_date = str_date(election.voting_end_date),
            authorities = dumps([auth.to_dict() for auth in election.authorities], indent=4)
        )
        approve_task = ExternalTask(label=label,
            data=info_text)
        task.add(approve_task)

        check_approval_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="check_tally_approval",
            queue="orchestra_performer",
            data=dict(election_id=election_id))
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
    election_id = input_data['election_id']
    privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
    approve_path = os.path.join(privdata_path, election_id, 'tally_approved')

    # create the tally_approved flag file
    open(approve_path, 'a').close()


@decorators.task(action="perform_tally", queue="verificatum_queue")
class PerformTallyTask(TaskHandler):
    def execute(self):
        '''
        Performs the tally in a synchronized way with the other authorities
        '''
        input_data = self.task.get_data()['input_data']
        sender_ssl_cert = self.task.get_data()['sender_ssl_cert']
        election_id = input_data['election_id']
        session_id = input_data['session_id']

        if not re.match("^[a-zA-Z0-9_-]+$", election_id):
            raise TaskError(dict(reason="invalid characters in election_id"))
        if not re.match("^[a-zA-Z0-9_-]+$", session_id):
            raise TaskError(dict(reason="invalid characters in session_id"))

        election = db.session.query(Election)\
            .filter(Election.id == election_id).first()
        if not election:
            raise TaskError(dict(reason="election not found"))

        # check sender is legitimate
        found_director = False
        for auth in election.authorities.all():
            if not certs_differ(auth.ssl_cert, sender_ssl_cert):
                found_director = True
        if not found_director:
            raise TaskError(dict(
                reason="perform tally task sent by an invalid authority"))

        privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
        election_privpath = os.path.join(privdata_path, election_id)
        session_privpath = os.path.join(election_privpath, session_id)
        tally_approved_path = os.path.join(election_privpath, 'tally_approved')

        # check that we have approved the tally
        autoaccept = app.config.get('AUTOACCEPT_REQUESTS', False)
        if not autoaccept:
            if not os.path.exists(tally_approved_path):
                raise TaskError(dict(reason="task not accepted"))
            os.unlink(tally_approved_path)

        subprocess.check_call(["vmn", "-mix", "privInfo.xml", "protInfo.xml",
            "ciphertexts_raw", "plaintexts_raw"], cwd=session_privpath)

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
    sender_ssl_cert = task.get_data()['sender_ssl_cert']
    input_data = task.get_data()['input_data']
    election_id = input_data['election_id']
    if not re.match("^[a-zA-Z0-9_-]+$", election_id):
        raise TaskError(dict(reason="invalid characters in election_id"))

    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if not election:
        raise TaskError(dict(reason="election not found"))

    # check sender is legitimate
    found_director = False
    for auth in election.authorities.all():
        if not certs_differ(auth.ssl_cert, sender_ssl_cert):
            found_director = True
    if not found_director:
        raise TaskError(dict(
            reason="perform tally task sent by an invalid authority"))

    privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(privdata_path, election_id)

    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, election_id)
    tally_path = os.path.join(election_pubpath, 'tally.tar.gz')
    tally_hash_path = os.path.join(election_pubpath, 'tally.tar.gz.sha512')

    # check election_pubpath already exists - it should contain pubkey etc
    if not os.path.exists(election_pubpath):
        raise TaskError(dict(reason="election public path doesn't exist"))

    # check no tally exists yet
    if os.path.exists(tally_path) and not election.is_recurring:
        raise TaskError(dict(reason="tally already exists"))

    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        plaintexts_raw_path = os.path.join(session_privpath, 'plaintexts_raw')
        plaintexts_json_path = os.path.join(session_privpath, 'plaintexts_json')
        proofs_path = os.path.join(session_privpath, 'dir', 'roProof')
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')

        # check that we have a tally
        if not os.path.exists(proofs_path) or not os.path.exists(plaintexts_raw_path):
            raise TaskError(dict(reason="proofs or plaintexts couldn't be verified"))

        # remove any previous plaintexts_json
        if os.path.exists(plaintexts_json_path):
            os.unlink(plaintexts_json_path)

        # transform plaintexts into json format
        subprocess.check_call(["vmnc", "-plain", "-outi", "json", "plaintexts_raw",
                            "plaintexts_json"], cwd=session_privpath)

        # verify the proofs. sometimes verificatum raises an exception at the end
        # so we dismiss it if the verification is successful. TODO: fix that in
        # verificatum
        try:
            output = subprocess.check_output(["vmnv", protinfo_path, proofs_path, "-v"])
        except subprocess.CalledProcessError, e:
            output = e.output
        if "Verification completed SUCCESSFULLY after" not in output:
            raise TaskError(dict(reason="invalid tally proofs"))

    result = tally.do_tally(election_privpath, json.loads(election.questions_data))
    result_privpath = os.path.join(election_privpath, 'result_json')
    with codecs.open(result_privpath, encoding='utf-8', mode='w') as res_f:
        res_f.write(json.dumps(result))

    # once the proofs have been verified, create and publish a tarball
    # containing plaintexts, protInfo and proofs
    # NOTE: we try our best to do a deterministic tally, i.e. one that can be
    # generated exactly the same bit by bit by all authorities

    # For example, here we open tarfile setting cwd so that the header of the
    # tarfile doesn't contain the full path, which would make the tally.tar.gz
    # not deterministic as it might vary from authority to authority
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(tally_path))
        tar = tarfile.open(os.path.basename(tally_path), 'w|gz')
    finally:
        os.chdir(cwd)
    timestamp = int(task.get_data()["created_date"].date().strftime("%s"))

    deterministic_tar_add(tar, result_privpath, 'result_json', timestamp)
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


    # and publish also the sha512 of the tarball
    tally_hash_file = open(tally_hash_path, 'w')
    tally_hash_file.write(hash_file(tally_path))
    tally_hash_file.close()

def deterministic_tarinfo(tfile, filepath, arcname, timestamp, uid=1000, gid=100):
    '''
    Creates a tarinfo with some fixed data
    '''
    tarinfo = tfile.gettarinfo(filepath, arcname)
    tarinfo.uid = uid
    tarinfo.gid = gid
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
        for subitem in os.listdir(filepath):
            newpath = os.path.join(filepath, subitem)
            newarcname = os.path.join(arcname, subitem)
            deterministic_tar_add(tfile, newpath, newarcname, timestamp, uid,
                gid)