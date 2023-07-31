#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import logging
import pickle
import base64
import json
from frestq.app import app, db
from frestq.utils import loads, dumps
from frestq.tasks import SimpleTask, TaskError
from .models import Election, Authority, QueryQueue
from .create_election.performer_jobs import check_election_data
import threading


def safe_dequeue():
    logging.debug("safe_dequeue(): starting")
    try:
        dequeue_task()
        return True
    except Exception as error:
        logging.debug(f"safe_dequeue(): exception {error}")
        return False

def start_queue(queue_continue=False):
    logging.debug(f"launching start_queue(queue_continue={queue_continue})")
    if not queue_continue:
        doing = db.session.query(QueryQueue).all()
        for i in doing:
            i.doing = False
            db.session.delete(i)
    else:
        doing = db.session.query(QueryQueue).filter(QueryQueue.doing == True)
        for i in doing:
            i.doing = False

    db.session.commit()
    t = threading.Thread(target=safe_dequeue)
    t.start()


def dequeue_task():
    logging.debug("dequeue_task(): starting")
    doing = db.session.query(QueryQueue).filter(QueryQueue.doing == True)
    todos = db.session.query(QueryQueue).filter(QueryQueue.doing == False)
    logging.debug(f"dequeue_task(): doing.count() = {doing.count()}")
    if not doing.count() and todos.count() > 0:
        logging.debug(f"dequeue_task(): getting next todo task")
        todo = db.session.query(QueryQueue)\
            .with_for_update(nowait=True, of=QueryQueue)\
            .order_by(QueryQueue.id)\
            .first()
        todo.doing = True
        logging.debug(f"dequeue_task(): todo.id = {todo.id}")
        db.session.commit()

        apply_task(todo.task, todo.data)
    else:
        logging.debug("no task to do")

def queue_task(task='election', data=None):
    data = data or {}
    d = json.dumps(data)
    qq = QueryQueue(task=task, data=d)
    db.session.add(qq)
    db.session.commit()
    safe_dequeue()
    return qq.id


def apply_task(task, data):
    logging.debug(f"apply_task(task={task}, data={data})")
    d = pickle.loads(base64.b64decode(data.encode('utf-8')))
    if task == 'election':
        r = election_task(d)
        if not r:
            end_task()

    if task == 'tally':
        r = tally_task(d)
        if not r:
            end_task()


def end_task():
    doing = db.session.query(QueryQueue)\
        .with_for_update(nowait=True)\
        .filter(QueryQueue.doing == True)\
        .one()
    db.session.delete(doing)
    db.session.commit()
    safe_dequeue()


### TASKS

def election_task(data):
    logging.debug(f"election_task(): running election_task..")
    if not data:
        logging.error(f"no data")
        return False

    try:
        check_election_data(data, True)
    except Exception as error:
        logging.error(f"election_task(): invalid json {error}")
        return False

    e = Election(
        id = data['id'],
        title = data['title'][:255],
        description = data['description'],
        questions = dumps(data['questions']),
        start_date = data['start_date'],
        end_date = data['end_date'],
        callback_url = data['callback_url'],
        num_parties = len(data['authorities']),
        threshold_parties = len(data['authorities']),
        status = 'creating'
    )
    db.session.add(e)

    for auth_data in data['authorities']:
        authority = Authority(
            name = auth_data['name'],
            ssl_cert = auth_data['ssl_cert'],
            orchestra_url = auth_data['orchestra_url'],
            election_id = data['id']
        )
        db.session.add(authority)
    db.session.commit()

    task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="create_election",
        queue="launch_task",
        data={
            'election_id': data['id']
        }
    )

    logging.error(f"election_task(): sending task..")
    task.create_and_send()
    return task


def tally_task(data):
    if not data:
        print("invalid json")
        return False

    requirements = [
        {'name': u'election_id', 'isinstance': int},
        {'name': u'callback_url', 'isinstance': str},
        {'name': u'votes_url', 'isinstance': str},
        {'name': u'votes_hash', 'isinstance': str},
    ]

    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
            req['isinstance']):
            print(req['name'], data.get(req['name'], None), type(data[req['name']]))
            print("invalid %s parameter" % req['name'])
            return False

    if data['election_id'] <= 0:
        print("election id must be >= 1")
        return False

    if not data['votes_hash'].startswith("ni:///sha-256;"):
        print("invalid votes_hash, must be sha256")
        return False

    election_id = data['election_id']
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if election is None:
        print("unknown election with election_id = %s" % election_id)
        return False

    task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="tally_election",
        queue="launch_task",
        data={
            'election_id': data['election_id'],
            'callback_url': data['callback_url'],
            'votes_url': data['votes_url'],
            'votes_hash': data['votes_hash'],
        }
    )
    task.create_and_send()
    return task
