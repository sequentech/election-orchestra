import pickle
import base64
import json
from frestq.app import app, db
from frestq.utils import loads, dumps
from frestq.tasks import SimpleTask, TaskError
from models import Election, Authority, QueryQueue
from create_election.performer_jobs import check_election_data
import threading


def safe_dequeue():
    try:
        dequeue_task()
        return True
    except Exception, e:
        return False

def start_queue(queue_continue=False):
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
    doing = db.session.query(QueryQueue).filter(QueryQueue.doing == True)
    if not doing.count():
        todo = db.session.query(QueryQueue).with_for_update(nowait=True, of=QueryQueue).order_by(QueryQueue.id).first()
        todo.doing = True
        db.session.commit()

        apply_task(todo.task, todo.data)


def queue_task(task='election', data=None):
    data = data or {}
    d = json.dumps(data)
    qq = QueryQueue(task=task, data=d)
    db.session.add(qq)
    db.session.commit()
    safe_dequeue()
    return qq.id


def apply_task(task, data):
    d = pickle.loads(base64.b64decode(data))
    if task == 'election':
        r = election_task(d)
        if not r:
            end_task()

    if task == 'tally':
        r = tally_task(d)
        if not r:
            end_task()


def end_task():
    doing = db.session.query(QueryQueue).with_for_update(nowait=True).filter(QueryQueue.doing == True).one()
    db.session.delete(doing)
    db.session.commit()
    safe_dequeue()


### TASKS

def election_task(data):
    if not data:
        print ("invalid json")
        return False

    try:
        check_election_data(data, True)
    except Exception, e:
        print("ERROR", e)
        return False

    e = Election(
        id = data['id'],
        title = data['title'],
        description = data['description'][:255],
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
    task.create_and_send()
    return task


def tally_task(data):
    if not data:
        print("invalid json")
        return False

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
