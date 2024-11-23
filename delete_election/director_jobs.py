# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import requests

from frestq import decorators
from frestq.utils import loads, dumps
from frestq.tasks import (SimpleTask, SequentialTask, TaskError)
from frestq.action_handlers import TaskHandler
from frestq.app import app, db

from models import Election
from reject_adapter import RejectAdapter
from taskqueue import end_task
 
@decorators.local_task
@decorators.task(action="delete_election", queue="launch_task")
class DeleteElectionTask(TaskHandler):
    def execute(self):
        task = self.task
        input_data = task.get_data()['input_data']
        election_id = input_data['election_id']
        election = db.session.query(Election)\
            .filter(Election.id == election_id).first()

        priv_info_task = SequentialTask()
        for authority in election.authorities:
            subtask = SimpleTask(
                receiver_url=authority.orchestra_url,
                receiver_ssl_cert=authority.ssl_cert,
                action="delete_private_info",
                queue="orchestra_performer",
                data=dict(
                    id=election_id,
                )
            )
            priv_info_task.add(subtask)
        task.add(priv_info_task)

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
            election = db.session.query(Election)\
                .filter(Election.id == election_id).first()

            session = requests.sessions.Session()
            callback_url = election.callback_url
            print("callback_url, " + callback_url)
            fail_data = {
                "status": "error",
                "reference": {
                    "election_id": election_id,
                    "action": "POST /delete"
                },
                "data": {
                    "message": "election deletion failed for some reason"
                }
            }
            ssl_calist_path = app.config.get('SSL_CALIST_PATH', '')
            ssl_cert_path = app.config.get('SSL_CERT_PATH', '')
            ssl_key_path = app.config.get('SSL_KEY_PATH', '')
            try:
                r = session.request(
                    'post',
                    callback_url,
                    data=dumps(fail_data),
                    headers={'content-type': 'application/json'},
                    verify=ssl_calist_path,
                    cert=(ssl_cert_path, ssl_key_path)
                )
            except Exception as post_error:
                print("exception calling to callback_url:")
                print(post_error)
                raise post_error
        finally:
            end_task()
