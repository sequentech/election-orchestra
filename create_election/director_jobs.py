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
import json
import codecs
import shutil
import requests
import binascii
import subprocess
import uuid

from frestq import decorators
from frestq.utils import loads, dumps
from frestq.tasks import (SimpleTask, ParallelTask, SequentialTask,
                          SynchronizedTask, TaskError)
from frestq.action_handlers import TaskHandler
from frestq.app import app, db

from models import Election, Authority, Session
from utils import mkdir_recursive
from vmn import *

@decorators.local_task
@decorators.task(action="create_election", queue="launch_task")
class CreateElectionTask(TaskHandler):
    def execute(self):
        task = self.task
        input_data = task.get_data()['input_data']
        election_id = input_data['election_id']
        election = db.session.query(Election)\
            .filter(Election.id == election_id).first()

        # 1. generate a session per question
        private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
        election_private_path = os.path.join(private_data_path, election_id)
        sessions = []
        questions_data = json.loads(election.questions_data)
        i = 0
        for question in questions_data:
            session_id = "%d-%s" % (i, str(uuid.uuid4()))
            # create stub.xml
            session_privpath = os.path.join(election_private_path, session_id)
            mkdir_recursive(session_privpath)
            # l = ["vmni", "-prot", "-sid", session_id, "-name",
            #    election.title, "-nopart", str(election.num_parties), "-thres",
            #    str(election.threshold_parties)]
            #subprocess.check_call(l, cwd=session_privpath)
            v_gen_protocol_info(session_id, election.title, election.num_parties,
                election.threshold_parties, session_privpath)

            # read stub file to be sent to all the authorities
            stub_path = os.path.join(session_privpath, 'stub.xml')
            stub_file = codecs.open(stub_path, 'r', encoding='utf-8')
            stub_content = stub_file.read()
            stub_file.close()

            sessions.append(dict(
                id=session_id,
                stub=stub_content
            ))
            session = Session(
                id=session_id,
                election_id=election_id,
                status='default',
                public_key='',
                question_number=i
            )
            db.session.add(session)

            i += 1
        db.session.commit()

        # 2. generate private info and protocol info files on each authority
        # (and for each question/session). Also, each authority might require
        # the approval of the task by its operator.
        priv_info_task = ParallelTask()
        for authority in election.authorities:
            subtask = SimpleTask(
                receiver_url=authority.orchestra_url,
                receiver_ssl_cert=authority.ssl_cert,
                action="generate_private_info",
                queue="orchestra_performer",
                data=dict(
                    election_id=election_id,
                    title = election.title,
                    url = election.url,
                    description = election.description,
                    sessions=sessions,
                    questions_data = election.questions_data,
                    voting_start_date = election.voting_start_date,
                    voting_end_date = election.voting_end_date,
                    is_recurring = election.is_recurring,
                    num_parties = election.num_parties,
                    threshold_parties = election.threshold_parties,
                    authorities=[a.to_dict() for a in election.authorities]
                )
            )
            priv_info_task.add(subtask)
        task.add(priv_info_task)

        # 3. merge the outputs into protInfo.xml files, send them to the
        # authorities, and generate pubkeys sequentially one session after the
        # other
        merge_protinfo_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="merge_protinfo",
            queue="orchestra_director",
            data=dict(
                election_id=election_id,
                session_ids=[s['id'] for s in sessions]
            )
        )
        task.add(merge_protinfo_task)

        # 4. send protInfo.xml to the original sender (we have finished!)
        return_election_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="return_election",
            queue="orchestra_director",
            data=dict(
                election_id=election_id,
                session_ids=[s['id'] for s in sessions]
            )
        )
        task.add(return_election_task)

    def handle_error(self, error):
        '''
        When an error is propagated up to here, is time to return to the sender
        that this task failed
        '''
        session = requests.sessions.Session()
        input_data = self.task.get_data()['input_data']
        election_id = input_data['election_id']
        election = db.session.query(Election)\
            .filter(Election.session_id == election_id).first()

        session = requests.sessions.Session()
        callback_url = election.callback_url
        fail_data = {
            "status": "error",
            "reference": {
                "election_id": election_id,
                "action": "POST /election"
            },
            "data": {
                "message": "election creation failed for some reason"
            }
        }
        r = session.request('post', callback_url, data=dumps(fail_data),
                            verify=False)


@decorators.task(action="merge_protinfo", queue="orchestra_director")
@decorators.local_task
def merge_protinfo_task(task):
    '''
    Merge the protinfos for each of the sessions (one session per question),
    and then create a pubkey for each protinfo
    '''
    input_data = task.get_data()['input_data']
    election_id = input_data['election_id']
    session_ids = input_data['session_ids']

    priv_info_task = task.get_prev()
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    questions_data = json.loads(election.questions_data)

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(private_data_path, election_id)

    i = 0

    # this task will contain one subtask of type SynchronizedTask to create
    # the pubkey for each session
    seq_task = SequentialTask()
    task.add(seq_task)
    for question in questions_data:
        j = 0
        # l = ["vmni", "-merge"]
        l = []
        session_id = session_ids[i]
        session_privpath = os.path.join(election_privpath, session_ids[i])

        # create protInfo<j>.xml files, extracting data from subtasks
        for subtask in priv_info_task.get_children():
            protinfo_content = subtask.get_data()['output_data'][i]
            protinfo_path = os.path.join(session_privpath, 'protInfo%d.xml' % j)
            l.append('protInfo%d.xml' % j)
            protinfo_file = codecs.open(protinfo_path, 'w', encoding='utf-8')
            protinfo_file.write(protinfo_content)
            protinfo_file.close()
            j += 1

        # merge the files
        # subprocess.check_call(l, cwd=session_privpath)
        v_merge(l, session_privpath)

        # read protinfo
        protinfo_path = os.path.join(session_privpath, 'protInfo.xml')
        protinfo_file = codecs.open(protinfo_path, 'r', encoding='utf-8')
        protinfo_content = protinfo_file.read()
        protinfo_file.close()

        # send protInfo.xml to the authorities and command them to cooperate in
        # the generation of the publicKey
        send_merged_protinfo = SynchronizedTask()
        seq_task.add(send_merged_protinfo)
        for authority in election.authorities:
            subtask = SimpleTask(
                receiver_url=authority.orchestra_url,
                action="generate_public_key",
                queue="verificatum_queue",
                data=dict(
                    session_id=session_id,
                    election_id=election_id,
                    protInfo_content=protinfo_content
                ),
                receiver_ssl_cert=authority.ssl_cert
            )
            send_merged_protinfo.add(subtask)

        i += 1

    return dict(
        output_data=protinfo_content
    )

@decorators.task(action="return_election", queue="orchestra_director")
@decorators.local_task
def return_election(task):
    input_data = task.get_data()['input_data']
    election_id = input_data['election_id']
    session_ids = input_data['session_ids']
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()

    session_data = []

    for session_id in session_ids:
        # read into a string the pubkey
        privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
        pubkey_path = os.path.join(privdata_path, election_id, session_id, 'publicKey_json')
        pubkey_file = open(pubkey_path, 'r')
        pubkey = pubkey_file.read()
        pubkey_file.close()
        session_data.append(dict(
            session_id=session_id,
            pubkey=json.loads(pubkey)
        ))

        # publish the pubkey
        pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
        pub_session_path = os.path.join(pubdata_path, election_id, session_id)
        pubkey_path2 = os.path.join(pub_session_path, 'publicKey_json')
        if not os.path.exists(pub_session_path):
            mkdir_recursive(pub_session_path)
        shutil.copyfile(pubkey_path, pubkey_path2)

        # publish protInfo.xml too
        session_privpath = os.path.join(privdata_path, election_id, session_id)
        protinfo_privpath = os.path.join(session_privpath, 'protInfo.xml')
        protinfo_pubpath = os.path.join(pub_session_path, 'protInfo.xml')
        shutil.copyfile(protinfo_privpath, protinfo_pubpath)

    session = requests.sessions.Session()
    callback_url = election.callback_url
    ret_data = {
        "status": "finished",
        "reference": {
            "election_id": election_id,
            "action": "POST /election"
        },
        "session_data": session_data
    }
    print "callback_url, ", callback_url
    print dumps(ret_data)
    r = session.request('post', callback_url, data=dumps(ret_data),
                        verify=False)
    print r.text