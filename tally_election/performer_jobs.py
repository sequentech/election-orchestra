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
import signal
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
from sha256 import hash_file

# we just use always the same timestamp for the files for creating
# deterministic tars
MAGIC_TIMESTAMP = 1394060400

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

@decorators.task(action="review_tally", queue="orchestra_performer")
def review_tally(task):
    '''
    Generates the local private info for a new election
    '''
    sender_ssl_cert = task.get_data()['sender_ssl_cert']
    data = task.get_data()['input_data']

    # check input data
    requirements = [
        {'name': u'election_id', 'isinstance': int},
        {'name': u'callback_url', 'isinstance': basestring},
        {'name': u'votes_url', 'isinstance': basestring},
        {'name': u'votes_hash', 'isinstance': basestring},
    ]

    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
                req['isinstance']):
            print req['name'], data.get(req['name'], None), type(data[req['name']])
            raise TaskError(dict(reason="invalid %s parameter" % req['name']))


    if data['election_id'] <= 0:
        raise TaskError(dict(reason="election_id must be a positive int"))

    if not data['votes_hash'].startswith("ni:///sha-256;"):
        raise TaskError(dict(reason="invalid votes_hash, must be sha256"))

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
    election_privpath = os.path.join(private_data_path, str(election_id))

    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, str(election_id))
    tally_path = os.path.join(election_pubpath, 'tally.tar.gz')

    if os.path.exists(tally_path):
        raise TaskError(dict(reason="election already tallied"))

    pubkeys = []
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

        pubkey_json_path = os.path.join(session_privpath, 'publicKey_json')
        with open(pubkey_json_path, 'r') as pubkey_file:
            pubkeys.append(json.loads(pubkey_file.read()))

        # reset securely
        #subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml",
        #    "-f"], cwd=session_privpath)
        v_reset(session_privpath)

    # if there were previous tallies, remove the tally approved flag file
    approve_path = os.path.join(private_data_path, str(election_id), 'tally_approved')
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
    input_hash = data['votes_hash'].replace('ni:///sha-256;', '')
    if not constant_time_compare(input_hash, hash_file(ciphertexts_path)):
        raise TaskError(dict(reason="invalid votes_hash"))

    # transform input votes into something readable by vfork. Basically
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

    # pubkeys needed to verify votes. we also save it to a file
    pubkeys_path = os.path.join(election_privpath, 'pubkeys_json')
    pubkeys_s = json.dumps(pubkeys,
        ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': '))
    with open(pubkeys_path, mode='w') as pubkeys_f:
        pubkeys_f.write(pubkeys_s)

    num_questions = len(election.sessions.all())
    invalid_votes = 0
    for qnum in range(num_questions):
        pubkeys[qnum]['g'] = int(pubkeys[qnum]['g'])
        pubkeys[qnum]['p'] = int(pubkeys[qnum]['p'])

    try:
        invotes_file = open(ciphertexts_path, 'r')
        for session in election.sessions.all():
            outvotes_path = os.path.join(election_privpath, session.id,
                'ciphertexts_json')
            outvotes_files.append(open(outvotes_path, 'w'))
        print("\n------ Reading and verifying POK of plaintext for the votes..\n")
        lnum = 0
        for line in invotes_file:
            lnum += 1
            line_data = json.loads(line)
            assert len(line_data['choices']) == len(outvotes_files)

            i = 0
            for choice in line_data['choices']:
                # NOTE: we use specific separators with no spaces, because
                # otherwise vfork won't read it well
                outvotes_files[i].write(json.dumps(choice,
                    ensure_ascii=False, sort_keys=True, separators=(',', ':')))
                outvotes_files[i].write("\n")
                i += 1
    finally:
        print("\n------ Verified %d votes in total (%d invalid)\n" % (lnum, invalid_votes))

        # save invalid votes
        invalid_votes_path = os.path.join(election_privpath, 'invalid_votes')
        with open(invalid_votes_path, 'w') as f:
          f.write("%d" % invalid_votes)

        if invotes_file is not None:
            invotes_file.close()
        for f in outvotes_files:
            f.close()

    # Convert each ciphertexts_json of each session into ciphertexts_raw
    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        #subprocess.check_call(["vmnc", "-ciphs", "-ini", "json",
        #    "ciphertexts_json", "ciphertexts_raw"], cwd=session_privpath)
        v_convert_ctexts_json(session_privpath)

    autoaccept = app.config.get('AUTOACCEPT_REQUESTS', False)
    if not autoaccept:
        def str_date(date):
            if date:
                return date.isoformat()
            else:
                return ""

        # request user to decide
        label = "approve_election_tally"
        info_text = {
          'Title': election.title,
          'Description': election.description,
          'Voting period': "%s - %s" % (str_date(election.start_date), str_date(election.end_date)),
          'Question data': loads(election.questions),
          'Authorities': [auth.to_dict() for auth in election.authorities]
        }
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
    approve_path = os.path.join(privdata_path, str(election_id), 'tally_approved')

    # create the tally_approved flag file
    open(approve_path, 'a').close()


@decorators.task(action="perform_tally", queue="vfork_queue")
class PerformTallyTask(TaskHandler):
    def execute(self):
        '''
        Performs the tally in a synchronized way with the other authorities
        '''
        input_data = self.task.get_data()['input_data']
        sender_ssl_cert = self.task.get_data()['sender_ssl_cert']
        election_id = input_data['election_id']
        session_id = input_data['session_id']

        if election_id <= 0:
            raise TaskError(dict(reason="invalid election_id, must be positive"))
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
        election_privpath = os.path.join(privdata_path, str(election_id))
        session_privpath = os.path.join(election_privpath, session_id)
        tally_approved_path = os.path.join(election_privpath, 'tally_approved')

        # check that we have approved the tally
        autoaccept = app.config.get('AUTOACCEPT_REQUESTS', False)
        if not autoaccept:
            if not os.path.exists(tally_approved_path):
                raise TaskError(dict(reason="task not accepted"))
            os.unlink(tally_approved_path)

        #call_cmd(["vmn", "-mix", "privInfo.xml", "protInfo.xml",
        #    "ciphertexts_raw", "plaintexts_raw"], cwd=session_privpath,
        #    timeout=5*3600, check_ret=0)

        def output_filter(p, o, output):
            '''
            detect common errors and kill process in that case
            '''
            if 'Exception in thread "main"' in o:
                p.kill(signal.SIGKILL)
                raise TaskError(dict(reason='error executing vfork'))

        v_mix(session_privpath, output_filter)

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
        #subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml", "-f"],
        #    cwd=election_private_path)
        try:
            v_reset(election_private_path)
        except Exception:
            print("cannot reset the tally, maybe it doesn't exists")


@decorators.task(action="verify_and_publish_tally", queue="orchestra_performer")
def verify_and_publish_tally(task):
    '''
    Once a tally has been performed, verify the result and if it's ok publish it
    '''
    sender_ssl_cert = task.get_data()['sender_ssl_cert']
    input_data = task.get_data()['input_data']
    election_id = input_data['election_id']
    if election_id <= 0:
        raise TaskError(dict(reason="election_id must be positive"))

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
    election_privpath = os.path.join(privdata_path, str(election_id))

    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, str(election_id))
    tally_path = os.path.join(election_pubpath, 'tally.tar.gz')
    tally_hash_path = os.path.join(election_pubpath, 'tally.tar.gz.sha256')

    # check election_pubpath already exists - it should contain pubkey etc
    if not os.path.exists(election_pubpath):
        raise TaskError(dict(reason="election public path doesn't exist"))

    # check no tally exists yet
    if os.path.exists(tally_path):
        raise TaskError(dict(reason="tally already exists, "
                             "election_id = %d" % election_id))

    pubkeys = []
    for session in election.sessions.all():
        session_privpath = os.path.join(election_privpath, session.id)
        plaintexts_raw_path = os.path.join(session_privpath, 'plaintexts_raw')
        plaintexts_json_path = os.path.join(session_privpath, 'plaintexts_json')
        proofs_path = os.path.join(session_privpath, 'dir', 'roProof')
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')

        pubkey_path = os.path.join(privdata_path, str(election_id), session.id, 'publicKey_json')
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

        # verify the proofs. sometimes vfork raises an exception at the end
        # so we dismiss it if the verification is successful. TODO: fix that in
        # vfork
        try:
            # output = subprocess.check_output(["vmnv", protinfo_path, proofs_path, "-v"])
            output = v_verify(protinfo_path, proofs_path)
        except subprocess.CalledProcessError, e:
            output = e.output
        if "Verification completed SUCCESSFULLY after" not in output:
            raise TaskError(dict(reason="invalid tally proofs"))

    # get number of invalid votes that were detected before decryption
    invalid_votes_path = os.path.join(election_privpath, 'invalid_votes')
    invalid_votes = int(open(invalid_votes_path, 'r').read(), 10)

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
        import time
        old_time = time.time
        time.time = lambda: MAGIC_TIMESTAMP
        tar = tarfile.open(os.path.basename(tally_path), 'w|gz')
    finally:
        time.time = old_time
        os.chdir(cwd)
    timestamp = MAGIC_TIMESTAMP

    ciphertexts_path = os.path.join(election_privpath, 'ciphertexts_json')
    pubkeys_path = os.path.join(privdata_path, str(election_id), 'pubkeys_json')
    questions_path = os.path.join(privdata_path, str(election_id), 'questions_json')

    with open(pubkeys_path, mode='w') as pubkeys_f:
        pubkeys_f.write(json.dumps(pubkeys,
            ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': ')))

    with codecs.open(questions_path, encoding='utf-8', mode='w') as res_f:
        res_f.write(json.dumps(json.loads(election.questions),
            ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': ')))

    deterministic_tar_add(tar, questions_path, 'questions_json', timestamp)
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
