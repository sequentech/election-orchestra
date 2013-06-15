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
import subprocess

from frestq import decorators
from frestq.tasks import SimpleTask, ParallelTask
from frestq.app import app, db

from models import Election, Authority
from utils import mkdir_recursive

@decorators.task(action="create_election", queue="orchestra_director")
def create_election(task):
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
    stub_file = open(stub_path, 'r')
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
                is_recurring = election.is_recurring,
                num_parties = election.num_parties,
                threshold_parties = election.threshold_parties,
                authorities=[a.to_dict() for a in election.authorities]
            )
        )
        priv_info_task.add(subtask)
    task.add(priv_info_task)

    # 3. merge the outputs into protInfo.xml
    merge_protinfo_task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="merge_protinfo_info",
        queue="orchestra_director",
        data=dict(
            session_id=session_id
        )
    )
    task.add(merge_protinfo_task)

    # 4. send protInfo.xml to the authorities

    # 5. send protInfo.xml to the original sender (we have finished!)

@decorators.task(action="merge_protinfo_info", queue="orchestra_director")
def merge_protinfo_task(task):
    # iterate on all priv info subtasks to merge them
    priv_info_task = task.get_prev()
    for subtask in priv_info_task.get_children():
        # TODO
        pass