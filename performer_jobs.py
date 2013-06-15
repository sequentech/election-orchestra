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
from utils import *

@decorators.task(action="generate_private_info", queue="orchestra_performer")
def generate_private_info(task):
    '''
    Generates the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']

    # 1. check this is a new election
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)
    protinfo_path = os.path.join(election_private_path, 'localProtInfo.xml')
    stub_path = os.path.join(election_private_path, 'stub.xml')

    # the election might actually exist if we're the director
    if os.path.exists(protinfo_path):
        return dict(
            output_data="election with session_id %s already exists" % session_id,
            output_status="error"
        )
    mkdir_recursive(election_private_path)

    # 2. create local data in the database

    # only create election if we are the director
    if not os.path.exists(stub_path):
        election = Election(
            session_id = input_data['session_id'],
            title = input_data['title'],
            is_recurring = input_data['is_recurring'],
            num_parties = input_data['num_parties'],
            threshold_parties = input_data['threshold_parties'],
        )
        db.session.add(election)
    else:
        election = db.session.query(Election)\
            .filter(Election.session_id == session_id).first()

    for auth_data in input_data['authorities']:
        authority = Authority(
            name = auth_data['name'],
            ssl_cert = auth_data['ssl_cert'],
            orchestra_url = auth_data['orchestra_url'],
            session_id = input_data['session_id']
        )
        db.session.add(authority)
    db.session.commit()

    # this are an "indicative" url, because port can vary later on
    server_url = get_server_url()
    hint_server_url = get_hint_server_url()

    # 3. copy stub.xml to private path
    stub_path = os.path.join(election_private_path, 'stub.xml')
    stub_file = open(stub_path, 'w')
    stub_content = stub_file.write(input_data['stub_content'])
    stub_file.close()

    # 4. generate localProtInfo.xml
    l = ["vmni", "-party", "-name", election.title, "-http",
        server_url, "-hint", hint_server_url]
    subprocess.check_call(l, cwd=election_private_path)

    # 5. read local protinfo file to be sent back to the orchestra director
    protinfo_file = open(stub_path, 'r')
    protinfo_content = protinfo_file.read()
    protinfo_file.close()

    return dict(
        output_data=protinfo_content
    )
