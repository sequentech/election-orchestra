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

import re
import os
import codecs
import subprocess
import json
from datetime import datetime

from frestq import decorators
from frestq.utils import dumps, loads
from frestq.tasks import SimpleTask, ParallelTask, ExternalTask, TaskError
from frestq.protocol import certs_differ
from frestq.app import app, db

from models import Election, Authority
from utils import *

def check_election_data(data, check_extra):
    '''
    check election input data. Used both in public_api.py:post_election and
    generate_private_info.
    '''
    requirements = [
        {'name': u'session_id', 'isinstance': basestring},
        {'name': u'title', 'isinstance': basestring},
        {'name': u'url', 'isinstance': basestring},
        {'name': u'description', 'isinstance': basestring},
        {'name': u'voting_start_date', 'isinstance': datetime},
        {'name': u'voting_end_date', 'isinstance': datetime},
        {'name': u'is_recurring', 'isinstance': bool},
        {'name': u'authorities', 'isinstance': list},
    ]

    if check_extra:
        requirements += [
            {'name': 'callback_url', 'isinstance': basestring},
            {'name': 'extra', 'isinstance': list},
            {'name': u'question_data', 'isinstance': dict},
        ]
    else:
        requirements += [
            {'name': u'question_data', 'isinstance': basestring},
        ]

    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
            req['isinstance']):
            print req['name'], data.get(req['name'], None), type(data[req['name']])
            raise TaskError(dict(reason="invalid %s parameter" % req['name']))

    if not re.match("^[a-zA-Z0-9_-]+$", data['session_id']):
        raise TaskError(dict(reason="invalid characters in session id"))

    if len(data['authorities']) == 0:
        raise TaskError(dict(reason='no authorities'))

    if Election.query.filter_by(session_id=data['session_id']).count() > 0:
        raise TaskError(dict(reason='an election with session id %s already '
            'exists' % data['session_id']))

    auth_reqs = [
        {'name': 'name', 'isinstance': basestring},
        {'name': 'orchestra_url', 'isinstance': basestring},
        {'name': 'ssl_cert', 'isinstance': basestring},
    ]

    for adata in data['authorities']:
        for req in auth_reqs:
            if req['name'] not in adata or not isinstance(adata[req['name']],
                req['isinstance']):
                raise TaskError(dict(reason="invalid %s parameter" % req['name']))

    def unique_by_keys(l, keys):
        for k in keys:
            if len(l) != len(set([i[k] for i in l])):
                return False
        return True

    if not unique_by_keys(data['authorities'], ['ssl_cert', 'orchestra_url']):
        raise TaskError(dict(reason="invalid authorities parameters"))

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

    # localProtInfo.xml should not exist
    if os.path.exists(protinfo_path):
        raise TaskError(dict(reason="election with session_id %s already exists" % session_id))
    mkdir_recursive(election_private_path)

    # 2. create local data in the database

    # only create election if we are not the director
    if certs_differ(task.get_data()['sender_ssl_cert'], app.config.get('SSL_CERT_STRING', '')):
        check_election_data(input_data, False)
        election = Election(
            session_id = input_data['session_id'],
            title = input_data['title'],
            url = input_data['url'],
            description = input_data['description'],
            question_data = input_data['question_data'],
            voting_start_date = input_data['voting_start_date'],
            voting_end_date = input_data['voting_end_date'],
            is_recurring = input_data['is_recurring'],
            num_parties = input_data['num_parties'],
            threshold_parties = input_data['threshold_parties'],
        )
        db.session.add(election)

        for auth_data in input_data['authorities']:
            if not os.path.exists(stub_path):
                authority = Authority(
                    name = auth_data['name'],
                    ssl_cert = auth_data['ssl_cert'],
                    orchestra_url = auth_data['orchestra_url'],
                    session_id = input_data['session_id']
                )
                db.session.add(authority)
        db.session.commit()
    else:
        election = db.session.query(Election)\
            .filter(Election.session_id == session_id).first()

    auth_name = None
    for auth_data in input_data['authorities']:
        if auth_data['orchestra_url'] == app.config.get('ROOT_URL', ''):
            auth_name = auth_data['name']

    # error, self not found
    if not auth_name:
        raise TaskError(dict(reason="trying to process what SEEMS to be an external election"))

    label = "approve_election"
    info_text = """* URL: %(url)s
* Title: %(title)s
* Description: %(description)s
* Voting period: %(start_date)s - %(end_date)s
* Question data: %(question_data)s
* Authorities: %(authorities)s""" % dict(
        url = input_data['url'],
        title = election.title,
        description = election.description,
        start_date = election.voting_start_date.isoformat(),
        end_date = election.voting_end_date.isoformat(),
        question_data = dumps(loads(input_data['question_data']), indent=4),
        authorities = dumps(input_data['authorities'], indent=4)
    )
    approve_task = ExternalTask(label=label,
        data=info_text)
    verificatum_task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="generate_private_info_verificatum",
        queue="orchestra_performer",
        data=dict())
    task.add(approve_task)
    task.add(verificatum_task)

@decorators.task(action="generate_private_info_verificatum", queue="orchestra_performer")
@decorators.local_task
def generate_private_info_verificatum(task):
    '''
    After the task has been approved, execute verificatum to generate the
    private info
    '''
    # first of all, check that parent task is approved. if that's not the case,
    # then cancel everythin
    if task.get_prev().get_data()['output_data'] != dict(status="accepted"):
        task.set_output_data("task not accepted")
        raise TaskError(dict(reason="task not accepted"))

    input_data = task.get_parent().get_data()['input_data']
    session_id = input_data['session_id']

    # 1. check this is a new election
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)
    protinfo_path = os.path.join(election_private_path, 'localProtInfo.xml')
    stub_path = os.path.join(election_private_path, 'stub.xml')
    election = db.session.query(Election)\
        .filter(Election.session_id == session_id).first()

    auth_name = None
    for auth_data in input_data['authorities']:
        if auth_data['orchestra_url'] == app.config.get('ROOT_URL', ''):
            auth_name = auth_data['name']

    # this are an "indicative" url, because port can vary later on
    server_url = get_server_url()
    hint_server_url = get_hint_server_url()

    # 3. copy stub.xml to private path
    stub_path = os.path.join(election_private_path, 'stub.xml')
    stub_file = codecs.open(stub_path, 'w', encoding='utf-8')
    stub_content = stub_file.write(input_data['stub_content'])
    stub_file.close()

    # 4. generate localProtInfo.xml
    l = ["vmni", "-party", "-name", auth_name, "-http",
        server_url, "-hint", hint_server_url]
    subprocess.check_call(l, cwd=election_private_path)

    # 5. read local protinfo file to be sent back to the orchestra director
    protinfo_file = codecs.open(protinfo_path, 'r', encoding='utf-8')
    protinfo_content = protinfo_file.read()
    protinfo_file.close()


    # set the output data of parent task, and update sender
    task.get_parent().set_output_data(protinfo_content,
                                      send_update_to_sender=True)

@decorators.task(action="generate_public_key", queue="verificatum_queue")
def generate_public_key(task):
    '''
    Generates the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, session_id)

    protinfo_path = os.path.join(election_private_path, 'protInfo.xml')
    if not os.path.exists(protinfo_path):
        protinfo_file = codecs.open(protinfo_path, 'w', encoding='utf-8')
        protinfo_file.write(input_data['protInfo_content'])
        protinfo_file.close()

    # generate raw public key
    subprocess.check_call(["vmn", "-keygen", "publicKey_raw"], cwd=election_private_path)

    # transform it into native format
    subprocess.check_call(["vmnc", "-pkey", "-outi", "native", "publicKey_raw",
                           "publicKey_native"], cwd=election_private_path)
