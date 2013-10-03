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
import codecs
import shutil
import requests
import binascii
import subprocess

from frestq import decorators
from frestq.utils import loads, dumps
from frestq.tasks import SimpleTask, ParallelTask, SynchronizedTask, TaskError
from frestq.action_handlers import TaskHandler
from frestq.app import app, db

from models import Election, Authority
from utils import mkdir_recursive

@decorators.local_task
@decorators.task(action="create_election", queue="orchestra_director")
class CreateElectionTask(TaskHandler):
    def execute(self):
        task = self.task
        input_data = task.get_data()['input_data']
        session_id = input_data['session_id']
        election = db.session.query(Election)\
            .filter(Election.session_id == session_id).first()

        private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
        election_private_path = os.path.join(private_data_path, session_id)
        mkdir_recursive(election_private_path)

        # 1. create stub.xml
        l = ["vmni", "-prot", "-sid", election.session_id, "-name",
            election.title, "-nopart", str(election.num_parties), "-thres",
            str(election.threshold_parties)]
        subprocess.check_call(l, cwd=election_private_path)

        # read stub file to be sent to all the authorities
        stub_path = os.path.join(election_private_path, 'stub.xml')
        stub_file = codecs.open(stub_path, 'r', encoding='utf-8')
        stub_content = stub_file.read()
        stub_file.close()

        # 2. generate private info and protocol info files on each authority
        priv_info_task = ParallelTask()
        for authority in election.authorities:
            subtask = SimpleTask(
                receiver_url=authority.orchestra_url,
                action="generate_private_info",
                queue="orchestra_performer",
                data=dict(
                    stub_content=stub_content,
                    session_id=session_id,
                    title = election.title,
                    url = election.url,
                    description = election.description,
                    question_data = election.question_data,
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

        # 3. merge the outputs into protInfo.xml and send them to the authorities,
        # then the authoritities will cooperativelly generate the publicKey
        merge_protinfo_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="merge_protinfo",
            queue="orchestra_director",
            data=dict(
                session_id=session_id
            )
        )
        task.add(merge_protinfo_task)

        # 5. send protInfo.xml to the original sender (we have finished!)
        return_election_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="return_election",
            queue="orchestra_director",
            data=dict(
                session_id=session_id
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
        session_id = input_data['session_id']
        election = db.session.query(Election)\
            .filter(Election.session_id == session_id).first()

        session = requests.sessions.Session()
        callback_url = election.callback_url
        fail_data = {
            "status": "error",
            "reference": {
                "session_id": session_id,
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
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']

    priv_info_task = task.get_prev()
    election = db.session.query(Election)\
        .filter(Election.session_id == session_id).first()

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)

    protinfo_path = os.path.join(election_private_path, 'localProtInfo.xml')

    # create protInfo<i>.xml files, extracting data from subtasks
    i = 1
    l = ["vmni", "-merge"]
    for subtask in priv_info_task.get_children():
        protinfo_content = subtask.get_data()['output_data']
        protinfo_path = os.path.join(election_private_path, 'protInfo%d.xml' % i)
        l.append('protInfo%d.xml' % i)
        protinfo_file = codecs.open(protinfo_path, 'w', encoding='utf-8')
        protinfo_file.write(protinfo_content)
        protinfo_file.close()
        i += 1

    # merge the files
    subprocess.check_call(l, cwd=election_private_path)

    # read protinfo
    protinfo_path = os.path.join(election_private_path, 'protInfo.xml')
    protinfo_file = codecs.open(protinfo_path, 'r', encoding='utf-8')
    protinfo_content = protinfo_file.read()
    protinfo_file.close()

    # send protInfo.xml to the authorities and command them to cooperate in
    # the generation of the publicKey
    send_merged_protinfo = SynchronizedTask()
    task.add(send_merged_protinfo)
    for authority in election.authorities:
        subtask = SimpleTask(
            receiver_url=authority.orchestra_url,
            action="generate_public_key",
            queue="verificatum_queue",
            data=dict(
                session_id=session_id,
                protInfo_content=protinfo_content
            ),
            receiver_ssl_cert=authority.ssl_cert
        )
        send_merged_protinfo.add(subtask)

    return dict(
        output_data=protinfo_content
    )

@decorators.task(action="return_election", queue="orchestra_director")
@decorators.local_task
def return_election(task):
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']
    protInfo_content = task.get_prev().get_data()['output_data']
    election = db.session.query(Election)\
        .filter(Election.session_id == session_id).first()

    # read into a string the pubkey
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    pubkey_path = os.path.join(private_data_path, session_id, 'publicKey_native')
    pubkey_file = open(pubkey_path, 'r')
    pubkey = pubkey_file.read()
    pubkey_file.close()

    # publish the pubkey
    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    pub_election_path = os.path.join(pubdata_path, session_id)
    pubkey_path2 = os.path.join(pub_election_path, 'publicKey_native')
    if not os.path.exists(pub_election_path):
        mkdir_recursive(pub_election_path)
    shutil.copyfile(pubkey_path, pubkey_path2)

    # publish protInfo.xml too
    election_private_path = os.path.join(private_data_path, session_id)
    protinfo_path = os.path.join(election_private_path, 'protInfo.xml')
    protinfo_path2 = os.path.join(pub_election_path, 'protInfo.xml')
    shutil.copyfile(protinfo_path, protinfo_path2)

    session = requests.sessions.Session()
    callback_url = election.callback_url
    ret_data = {
        "status": "finished",
        "reference": {
            "session_id": session_id,
            "action": "POST /election"
        },
        "data": {
            "protinfo": protInfo_content,
            "publickey": pubkey
        }
    }
    r = session.request('post', callback_url, data=dumps(ret_data),
                        verify=False)
