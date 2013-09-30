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

from flask import Blueprint, request, make_response, abort
import json
from datetime import datetime

from frestq.utils import loads, dumps
from frestq.tasks import SimpleTask, TaskError
from frestq.app import app, db

from models import Election, Authority
from create_election.performer_jobs import check_election_data

public_api = Blueprint('public_api', __name__)

def error(status, message=""):
    if message:
        data = json.dumps(dict(message=message))
    else:
        data=""
    return make_response(data, status)

@public_api.route('/election', methods=['POST'])
def post_election():
    '''
    POST /election

    Creates an election, with the given input data. This involves communicating
    with the different election authorities to generate the joint public key.

    Example request:
    POST /election
    {
        "session_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
        "is_recurring": false,
        "callback_url": "http://example.com/callback_create_election",
        "extra": [],
        "title": "New Directive Board",
        "url": "https://example.com/election/url",
        "description": "election description",
        "question_data": {
            "question": "Who Should be President?",
            "tally_type": "ONE_CHOICE",
            "answers": ["Alice", "Bob"],
            "max": 1, "min": 0
        },
        "voting_start_date": "2012-12-06T18:17:14.457000",
        "voting_end_date": "2012-12-06T18:17:14.457000",
        "authorities": [
            {
                "name": "Asociación Sugus GNU/Linux",
                "orchestra_url": "https://sugus.eii.us.es/orchestra",
                "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIFATCCA+mgAwIBAgIQAOli4NZQEWpKZeYX25jjwDANBgkqhkiG9w0BAQUFADBz\n8YOltJ6QfO7jNHU9jh/AxeiRf6MibZn6fvBHvFCrVBvDD43M0gdhMkVEDVNkPaak\nC7AHA/waXZ2EwW57Chr2hlZWAkwkFvsWxNt9BgJAJJt4CIVhN/iau/SaXD0l0t1N\nT0ye54QPYl38Eumvc439Yd1CeVS/HYbP0ISIfpNkkFA5TiQdoA==\n-----END CERTIFICATE-----"
            },
            {
                "name": "Agora Ciudadana",
                "orchestra_url": "https://agoravoting.com:6874/orchestra",
                "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIFATCCA+mgAwIBAgIQAOli4NZQEWpKZeYX25jjwDANBgkqhkiG9w0BAQUFADBz\n8YOltJ6QfO7jNHU9jh/AxeiRf6MibZn6fvBHvFCrVBvDD43M0gdhMkVEDVNkPaak\nC7AHA/waXZ2EwW57Chr2hlZWAkwkFvsWxNt9BgJAJJt4CIVhN/iau/SaXD0l0t1N\nT0ye54QPYl38Eumvc439Yd1CeVS/HYbP0ISIfpNkkFA5TiQdoA==\n-----END CERTIFICATE-----"
            },
            {
                "name": "Wadobo Labs",
                "orchestra_url": "https://wadobo.com:6874/orchestra",
                "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIFATCCA+mgAwIBAgIQAOli4NZQEWpKZeYX25jjwDANBgkqhkiG9w0BAQUFADBz\n8YOltJ6QfO7jNHU9jh/AxeiRf6MibZn6fvBHvFCrVBvDD43M0gdhMkVEDVNkPaak\nC7AHA/waXZ2EwW57Chr2hlZWAkwkFvsWxNt9BgJAJJt4CIVhN/iau/SaXD0l0t1N\nT0ye54QPYl38Eumvc439Yd1CeVS/HYbP0ISIfpNkkFA5TiQdoA==\n-----END CERTIFICATE-----"
            }
        ]
    }

        The parameter "extra" allows to modify the protocol settings for the
        stub.xml that is generated with verificatum's vmni command. Please
        refer to verificatum documentation for more details.

        On success, response is empty with status 202 Accepted. When the
        election finally gets processed, the callback_url is called with a POST
        containing directly the protInfo.xml file generated jointly by each
        authority.

        Note that this protInfo.xml will contain the election public key, but
        also some other information. In particular, it's worth noting that
        the http and hint servers' urls for each authority could change later,
        if election-orchestra needs it.
    '''
    try:
        data = loads(request.data)
    except:
        return error(400, "invalid json")

    try:
        check_election_data(data, True)
    except TaskError, e:
        print e
        return error(400, e.data['reason'])

    e = Election(
        session_id = data['session_id'],
        title = data['title'],
        url = data['url'],
        description = data['description'],
        question_data = dumps(data['question_data']),
        voting_start_date = data['voting_start_date'],
        voting_end_date = data['voting_end_date'],
        is_recurring = data['is_recurring'],
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
            session_id = data['session_id']
        )
        db.session.add(authority)
    db.session.commit()

    task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="create_election",
        queue="orchestra_director",
        data={
            'session_id': data['session_id']
        }
    )
    task.create_and_send()

    return make_response(dumps(dict(task_id=task.get_data()['id'])), 202)

@public_api.route('/receive_election', methods=['POST'])
def receive_election():
    '''
    This is a test route to be able to test that callbacks are correctly sent
    '''
    print "ATTENTION received election callback: "
    print request.data
    return make_response("", 202)
