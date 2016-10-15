# -*- coding: utf-8 -*-

# This file is part of election-orchestra.
# Copyright (C) 2013-2016  Agora Voting SL <agora@agoravoting.com>

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
import shutil
import signal
from datetime import datetime

from frestq import decorators
from frestq.utils import dumps, loads
from frestq.tasks import SimpleTask, ParallelTask, ExternalTask, TaskError
from frestq.protocol import certs_differ
from frestq.app import app, db

from models import Election, Authority, Session
from utils import *
from vmn import *

def check_pipe(requirements, l):
    for req in requirements:
        for data in l:
            if req['name'] not in data or not isinstance(data[req['name']],
                req['isinstance']):
                return False
    return True

def pluck(l, key):
    return [i[key] for i in l]

def check_election_data(data, check_extra):
    '''
    check election input data. Used both in public_api.py:post_election and
    generate_private_info.
    '''
    requirements = [
        {'name': u'id', 'isinstance': int},
        {'name': u'title', 'isinstance': basestring},
        {'name': u'description', 'isinstance': basestring},
        {'name': u'authorities', 'isinstance': list},
    ]

    if check_extra:
        requirements += [
            {'name': 'callback_url', 'isinstance': basestring},
            {'name': u'questions', 'isinstance': list},
        ]
        questions = data.get('questions', None)
    else:
        try:
            questions = json.loads(data.get('questions', None))
        except:
            raise TaskError(dict(reason='questions is not in json'))

    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
            req['isinstance']):
            raise TaskError(dict(reason="invalid %s parameter" % req['name']))

    if 'start_date' not in data or (data['start_date'] is not None
            and not isinstance(data['start_date'], datetime)):
        raise TaskError(dict(reason="invalid start_date parameter"))

    if 'end_date' not in data or (data['end_date'] is not None
            and not isinstance(data['end_date'], datetime)):
        raise TaskError(dict(reason="invalid end_date parameter"))

    if data['id'] < 1:
        raise TaskError(dict(reason="id must be positive"))

    if len(data['authorities']) == 0:
        raise TaskError(dict(reason='no authorities'))

    if not isinstance(questions, list) or len(questions) < 1 or\
            len(questions) > app.config.get('MAX_NUM_QUESTIONS_PER_ELECTION', 15):
        raise TaskError(dict(reason='Unsupported number of questions in the election'))


    if check_extra and\
            Election.query.filter_by(id=data['id']).count() > 0:
        raise TaskError(dict(reason='an election with id %s already '
            'exists' % data['id']))

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

    q_reqs = [
        {'name': 'text', 'isinstance': basestring},
        {'name': 'id', 'isinstance': int},
    ]

    task_error = TaskError(dict(reason="invalid question/answers"))
    questions = data['questions']
    if isinstance(questions, basestring):
        questions = json.loads(questions)

    for question in questions:
        answers = question['answers']
        if not unique_by_keys(answers, ['id', 'text']):
            raise task_error

        if not check_pipe(q_reqs, answers):
            raise task_error

        l_ids = pluck(answers, 'id')
        if set(l_ids) != set(range(0, len(l_ids))):
            raise task_error


@decorators.task(action="generate_private_info", queue="orchestra_performer")
def generate_private_info(task):
    '''
    Generates the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    election_id = input_data['id']

    # 1. check this is a new election and check input data
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(private_data_path, str(election_id))

    # check generic input data, similar to the data for public_api
    check_election_data(input_data, False)

    # check the sessions data
    if not isinstance(input_data.get('sessions', None), list) or\
            not len(input_data['sessions']):
        raise TaskError(dict(reason="No sessions provided"))
    for session in input_data['sessions']:
        if not isinstance(session, dict) or 'id' not in session or\
                'stub' not in session or\
                not isinstance(session['stub'], basestring) or\
                not re.match("^[a-zA-Z0-9_-]+$", session['id']):
            raise TaskError(dict(reason="Invalid session data provided"))


    # check that we are indeed one of the listed authorities
    auth_name = None
    for auth_data in input_data['authorities']:
        if auth_data['orchestra_url'] == app.config.get('ROOT_URL', ''):
            auth_name = auth_data['name']
    if not auth_name:
        raise TaskError(dict(reason="trying to process what SEEMS to be an external election"))

    # localProtInfo.xml should not exist for any of the sessions, as our task is
    # precisely to create it. note that we only check that localProtInfo.xml
    # files don't exist, because if we are the director, then the stub and
    # parent directory will already exist
    for session in input_data['sessions']:
        session_privpath = os.path.join(election_privpath, session['id'])
        protinfo_path = os.path.join(session_privpath, 'localProtInfo.xml')
        if os.path.exists(protinfo_path):
            raise TaskError(dict(reason="session_id %s already created" % session['id']))

    # 2. create base local data from received input in case it's needed:
    # create election models, dirs and stubs if we are not the director
    if certs_differ(task.get_data()['sender_ssl_cert'], app.config.get('SSL_CERT_STRING', '')):
        if os.path.exists(election_privpath):
            raise TaskError(dict(reason="Already existing election id %d" % input_data['id']))
        election = Election(
            id = input_data['id'],
            title = input_data['title'],
            description = input_data['description'],
            questions = input_data['questions'],
            start_date = input_data['start_date'],
            end_date = input_data['end_date'],
            num_parties = input_data['num_parties'],
            threshold_parties = input_data['threshold_parties'],
        )
        db.session.add(election)

        for auth_data in input_data['authorities']:
            authority = Authority(
                name = auth_data['name'],
                ssl_cert = auth_data['ssl_cert'],
                orchestra_url = auth_data['orchestra_url'],
                election_id = input_data['id']
            )
            db.session.add(authority)

        # create dirs and stubs, and session model
        i = 0
        for session in input_data['sessions']:
            session_model = Session(
                id=session['id'],
                election_id=election_id,
                status='default',
                public_key='',
                question_number=i
            )
            db.session.add(session_model)

            session_privpath = os.path.join(election_privpath, session['id'])
            mkdir_recursive(session_privpath)
            stub_path = os.path.join(session_privpath, 'stub.xml')
            stub_file = codecs.open(stub_path, 'w', encoding='utf-8')
            stub_content = stub_file.write(session['stub'])
            stub_file.close()
            i += 1
        db.session.commit()
    else:
        # if we are the director, models, dirs and stubs have been created
        # already, so we just get the election from the database
        election = db.session.query(Election)\
            .filter(Election.id == election_id).first()

    # only create external task if we have configured autoaccept to false in
    # settings:
    autoaccept = app.config.get('AUTOACCEPT_REQUESTS', '')
    if not autoaccept:
        def str_date(date):
            if date:
                return date.isoformat()
            else:
                return ""

        label = "approve_election"
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

    vfork_task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="generate_private_info_vfork",
        queue="orchestra_performer",
        data=dict())
    task.add(vfork_task)

@decorators.task(action="generate_private_info_vfork", queue="orchestra_performer")
@decorators.local_task
def generate_private_info_vfork(task):
    '''
    After the task has been approved, execute vfork to generate the
    private info
    '''
    # first of all, check that parent task is approved, but we only check that
    # when autoaccept is configured to False. if that's not the case,
    # then cancel everything
    autoaccept = app.config.get('AUTOACCEPT_REQUESTS', '')
    if not autoaccept and\
            task.get_prev().get_data()['output_data'] != dict(status="accepted"):
        task.set_output_data("task not accepted")
        raise TaskError(dict(reason="task not accepted"))

    input_data = task.get_parent().get_data()['input_data']
    election_id = input_data['id']
    sessions = input_data['sessions']
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()

    auth_name = None
    for auth_data in input_data['authorities']:
        if auth_data['orchestra_url'] == app.config.get('ROOT_URL', ''):
            auth_name = auth_data['name']

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(private_data_path, str(election_id))

    # this are an "indicative" url, because port can vary later on
    server_url = get_server_url()
    hint_server_url = get_hint_server_url()

    # generate localProtInfo.xml
    protinfos = []
    for session in sessions:
        session_privpath = os.path.join(election_privpath, session['id'])
        protinfo_path = os.path.join(session_privpath, 'localProtInfo.xml')
        stub_path = os.path.join(session_privpath, 'stub.xml')

        #l = ["vmni", "-party", "-arrays", "file", "-name", auth_name, "-http",
        #    server_url, "-hint", hint_server_url]
        #subprocess.check_call(l, cwd=session_privpath)
        v_gen_private_info(auth_name, server_url, hint_server_url, session_privpath)

        # 5. read local protinfo file to be sent back to the orchestra director
        protinfo_file = codecs.open(protinfo_path, 'r', encoding='utf-8')
        protinfos.append(protinfo_file.read())
        protinfo_file.close()

    # set the output data of parent task, and update sender
    task.get_parent().set_output_data(protinfos)

@decorators.task(action="generate_public_key", queue="vfork_queue")
def generate_public_key(task):
    '''
    Generates the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    session_id = input_data['session_id']
    election_id = input_data['election_id']

    privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
    session_privpath = os.path.join(privdata_path, str(election_id), session_id)

    # some sanity checks, as this is not a local task
    if not os.path.exists(session_privpath):
        raise TaskError(dict(reason="invalid session_id / election_id: " + session_privpath))
    if os.path.exists(os.path.join(session_privpath, 'publicKey_raw')) or\
            os.path.exists(os.path.join(session_privpath, 'publicKey_json')):
        raise TaskError(dict(reason="pubkey already created"))

    # if it's not local, we have to create the merged protInfo.xml
    protinfo_path = os.path.join(session_privpath, 'protInfo.xml')
    if not os.path.exists(protinfo_path):
        protinfo_file = codecs.open(protinfo_path, 'w', encoding='utf-8')
        protinfo_file.write(input_data['protInfo_content'])
        protinfo_file.close()

    # generate raw public key
    def output_filter(p, o, output):
        '''
        detect common errors and kill process in that case
        '''
        if "Unable to download signature!" in o or\
                "ERROR: Invalid socket address!" in o:
            p.kill(signal.SIGKILL)
            raise TaskError(dict(reason='error executing vfork'))

    #call_cmd(["vmn", "-keygen", "publicKey_raw"], cwd=session_privpath,
    #         timeout=10*60, check_ret=0, output_filter=output_filter)
    v_gen_public_key(session_privpath, output_filter)


    def output_filter2(p, o, output):
        '''
        detect common errors and kill process in that case
        '''
        if "Failed to parse info files!" in o:
            p.kill(signal.SIGKILL)
            raise TaskError(dict(reason='error executing vfork'))

    # transform it into json format
    #call_cmd(["vmnc", "-pkey", "-outi", "json", "publicKey_raw",
    #          "publicKey_json"], cwd=session_privpath,
    #          timeout=20, check_ret=0)
    v_convert_pkey_json(session_privpath, output_filter)

    # publish protInfo.xml and publicKey_json
    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    session_pubpath = os.path.join(pubdata_path, str(election_id), session_id)
    if not os.path.exists(session_pubpath):
        mkdir_recursive(session_pubpath)

    pubkey_privpath = os.path.join(session_privpath, 'publicKey_json')
    pubkey_pubpath = os.path.join(session_pubpath, 'publicKey_json')
    shutil.copyfile(pubkey_privpath, pubkey_pubpath)

    protinfo_privpath = os.path.join(session_privpath, 'protInfo.xml')
    protinfo_pubpath = os.path.join(session_pubpath, 'protInfo.xml')
    shutil.copyfile(protinfo_privpath, protinfo_pubpath)
