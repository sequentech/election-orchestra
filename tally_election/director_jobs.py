# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import os
import codecs
import requests
import subprocess

from frestq import decorators
from frestq.utils import loads, dumps
from frestq.tasks import (SimpleTask, ParallelTask, SequentialTask,
                          SynchronizedTask, TaskError)
from frestq.action_handlers import TaskHandler, SynchronizedTaskHandler
from frestq.app import app, db

from models import Election, Authority, Session
from reject_adapter import RejectAdapter
from utils import mkdir_recursive

from taskqueue import end_task

@decorators.local_task
@decorators.task(action="tally_election", queue="launch_task")
class TallyElectionTask(TaskHandler):
    def execute(self):
        data = self.task.get_data()['input_data']
        election_id = data['election_id']
        election = db.session.query(Election)\
            .filter(Election.id == election_id).first()

        session_ids = [s.id for s in db.session.query(Session).\
                with_parent(election,"sessions").\
                order_by(Session.question_number)]

        if 1:
            raise TaskError(dict(reason="Felix was here YY1"))

        # 1. let all authorities download the votes and review the requested
        # tally
        parallel_task = ParallelTask()
        for authority in election.authorities:
            review_task = SimpleTask(
                receiver_url=authority.orchestra_url,
                action="review_tally",
                queue="orchestra_performer",
                data={
                    'election_id': data['election_id'],
                    'callback_url': data['callback_url'],
                    'votes_url': data['votes_url'],
                    'votes_hash': data['votes_hash'],
                },
                receiver_ssl_cert=authority.ssl_cert
            )
            parallel_task.add(review_task)
        self.task.add(parallel_task)

        # 2. once all the authorities have reviewed and accepted the tallies
        # (one per question/session), launch mixnet to perform it
        seq_task = SequentialTask()
        self.task.add(seq_task)
        for session_id in session_ids:
            sync_task = SynchronizedTask()
            seq_task.add(sync_task)
            for authority in election.authorities:
                auth_task = SimpleTask(
                    receiver_url=authority.orchestra_url,
                    action="perform_tally",
                    queue="mixnet_queue",
                    data={
                        'election_id': data['election_id'],
                        'session_id': session_id
                    },
                    receiver_ssl_cert=authority.ssl_cert
                )
                sync_task.add(auth_task)

        # once the mixing phase has been done, let all the authorities verify
        # the results and publish them
        parallel_task = ParallelTask()
        for authority in election.authorities:
            review_task = SimpleTask(
                receiver_url=authority.orchestra_url,
                action="verify_and_publish_tally",
                queue="orchestra_performer",
                data={
                    'election_id': data['election_id'],
                    'session_ids': session_ids,
                },
                receiver_ssl_cert=authority.ssl_cert
            )
            parallel_task.add(review_task)
        self.task.add(parallel_task)

        # finally, send the tally to the callback_url
        ret_task = SimpleTask(
            receiver_url=app.config.get('ROOT_URL', ''),
            action="return_tally",
            queue="orchestra_director",
            data={"empty": "empty"}
        )
        self.task.add(ret_task)

    def handle_error(self, error):
        '''
        When an error is propagated up to here, is time to return to the sender
        that this task failed
        '''
        try:
            session = requests.sessions.Session()
            session.mount('http://', RejectAdapter())
            input_data = self.task.get_data()['input_data']
            election_id = input_data['election_id']
            callback_url = input_data['callback_url']
            election = db.session.query(Election)\
                .filter(Election.id == election_id).first()

            session = requests.sessions.Session()
            fail_data = {
                "status": "error",
                "reference": {
                    "election_id": election_id,
                    "action": "POST /tally"
                },
                "data": {
                    "message": "election tally failed for some reason"
                }
            }
            ssl_calist_path = app.config.get('SSL_CALIST_PATH', '')
            ssl_cert_path = app.config.get('SSL_CERT_PATH', '')
            ssl_key_path = app.config.get('SSL_KEY_PATH', '')
            print("\nFF callback_url4 " + callback_url)
            r = session.request(
                'post', 
                callback_url, 
                data=dumps(fail_data), 
                headers={'content-type': 'application/json'},
                verify=ssl_calist_path, 
                cert=(ssl_cert_path, ssl_key_path)
            )
            print(r.text)
        finally:
            end_task()


@decorators.local_task
@decorators.task(action="return_tally", queue="orchestra_director")
def return_election(task):
    input_data = task.get_parent().get_data()['input_data']
    election_id = input_data['election_id']
    callback_url = input_data['callback_url']

    pub_data_url = app.config.get('PUBLIC_DATA_BASE_URL', '')
    tally_url = pub_data_url + '/' + str(election_id) + '/tally.tar.gz'

    pub_data_path = app.config.get('PUBLIC_DATA_PATH', '')
    tally_hash_path = os.path.join(
        pub_data_path, 
        str(election_id), 
        'tally.tar.gz.sha256'
    )

    f = open(tally_hash_path, 'r')
    tally_hash = f.read()
    f.close()

    ret_data = {
        "status": "finished",
        "reference": {
            "election_id": election_id,
            "action": "POST /tally"
        },
        "data": {
            "tally_url": tally_url,
            "tally_hash": "ni:///sha-256;" + tally_hash
        }
    }
    session = requests.sessions.Session()
    session.mount('http://', RejectAdapter())
    ssl_calist_path = app.config.get('SSL_CALIST_PATH', '')
    ssl_cert_path = app.config.get('SSL_CERT_PATH', '')
    ssl_key_path = app.config.get('SSL_KEY_PATH', '')
    print("\nFF callback_url5 " + callback_url)
    r = session.request(
        'post', 
        callback_url, 
        data=dumps(ret_data), 
        headers={'content-type': 'application/json'},
        verify=ssl_calist_path, 
        cert=(ssl_cert_path, ssl_key_path)
    )
    print(r.text)
    end_task()
