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


import json
import re
from datetime import datetime

from flask import Blueprint, request, make_response, abort

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
      "id": 1110,
      "title": "Votación de candidatos",
      "description": "Selecciona los documentos polí­tico, ético y organizativo con los que Podemos",
      "director": "wadobo-auth1",
      "authorities": "openkratio-authority",
      "layout": "pcandidates-election",
      "presentation": {
        "share_text": "lo que sea",
        "theme": "foo",
        "urls": [
          {
            "title": "",
            "url": ""
          }
        ],
        "theme_css": "whatever"
      },
      "end_date": "2013-12-09T18:17:14.457000",
      "start_date": "2013-12-06T18:17:14.457000",
      "questions": [
          {
              "description": "",
              "layout": "pcandidates-election",
              "max": 1,
              "min": 0,
              "num_winners": 1,
              "title": "Secretarí­a General",
              "randomize_answer_order": true,
              "tally_type": "plurality-at-large",
              "answer_total_votes_percentage": "over-total-valid-votes",
              "answers": [
                {
                  "id": 0,
                  "category": "Equipo de Enfermeras",
                  "details": "",
                  "sort_order": 1,
                  "urls": [
                    {
                      "title": "",
                      "url": ""
                    }
                  ],
                  "text": "Fulanita de tal",
                }
              ]
          }
      ],
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


    On success, response is empty with status 202 Accepted and returns something
    like:

    {
        "task_id": "ba83ee09-aa83-1901-bb11-e645b52fc558",
    }
    When the election finally gets processed, the callback_url is called with a
    POST containing the protInfo.xml file generated jointly by each
    authority, following this example response:

    {
        "status": "finished",
        "reference": {
            "election_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
            "action": "POST /election"
        },
        "session_data": [{
            "session_id": "deadbeef-03fa-4890-aa83-2fc558e645b5",
            "publickey": ["<pubkey codified in hexadecimal>"]
        }]
    }

    Note that this protInfo.xml will contain the election public key, but
    also some other information. In particular, it's worth noting that
    the http and hint servers' urls for each authority could change later,
    if election-orchestra needs it.

    If there was an error, then the callback will be called following this
    example format:

    {
        "status": "error",
        "reference": {
            "session_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
            "action": "POST /election"
        },
        "data": {
            "message": "error message"
        }
    }
    '''
    data = request.get_json(force=True, silent=True)
    if not data:
        return error(400, "invalid json")

    try:
        check_election_data(data, True)
    except TaskError, e:
        print e
        return error(400, e.data['reason'])

    e = Election(
        id = data['id'],
        title = data['title'],
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
    task.create_and_send()

    return make_response(dumps(dict(task_id=task.get_data()['id'])), 202)


@public_api.route('/tally', methods=['POST'])
def post_tally():
    '''
    POST /tally

    Tallies an election, with the given input data. This involves communicating
    with the different election authorities to do the tally.

    Example request:
    POST /tally
    {
        "election_id": 111,
        "callback_url": "https://127.0.0.1:5000/public_api/receive_tally",
        "votes_url": "https://127.0.0.1:5000/public_data/vota4/encrypted_ciphertexts",
        "votes_hash": "ni:///sha-256;f4OxZX_x_FO5LcGBSKHWXfwtSx-j1ncoSt3SABJtkGk"
    }

    On success, response is empty with status 202 Accepted and returns something
    like:

    {
        "task_id": "ba83ee09-aa83-1901-bb11-e645b52fc558",
    }

    When the election finally gets processed, the callback_url is called with POST
    similar to the following example:

    {
        "status": "finished",
        "reference": {
            "election_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
            "action": "POST /tally"
        },
        "data": {
            "votes_url": "https://127.0.0.1:5000/public_data/vota4/tally.tar.bz2",
            "votes_hash": "ni:///sha-256;f4OxZX_x_FO5LcGBSKHWXfwtSx-j1ncoSt3SABJtkGk"
        }
    }

    If there was an error, then the callback will be called following this
    example format:

    {
        "status": "error",
        "reference": {
            "election_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
            "action": "POST /tally"
        },
        "data": {
            "message": "error message"
        }
    }
    '''

    # first of all, parse input data
    data = request.get_json(force=True, silent=True)
    if not data:
        return error(400, "invalid json")
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
            return error(400, "invalid %s parameter" % req['name'])

    if data['election_id'] <= 0:
        return error(400, "election id must be >= 1")

    if not data['votes_hash'].startswith("ni:///sha-256;"):
        return error(400, "invalid votes_hash, must be sha256")

    election_id = data['election_id']
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if election is None:
        return error(400, "unknown election with election_id = %s" % election_id)

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
    return make_response(dumps(dict(task_id=task.get_data()['id'])), 202)

@public_api.route('/receive_election', methods=['POST'])
def receive_election():
    '''
    This is a test route to be able to test that callbacks are correctly sent
    '''
    print "ATTENTION received election callback: "
    print request.get_json(force=True, silent=True)
    return make_response("", 202)


@public_api.route('/receive_tally', methods=['POST'])
def receive_tally():
    '''
    This is a test route to be able to test that callbacks are correctly sent
    '''
    print "ATTENTION received tally callback: "
    print request.get_json(force=True, silent=True)
    return make_response("", 202)
