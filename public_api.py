# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Agora Voting SL <contact@nvotes.com>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import pickle
import base64
import json
import re
from datetime import datetime

from flask import Blueprint, request, make_response, abort

from frestq.utils import loads, dumps
from frestq.tasks import SimpleTask, TaskError
from frestq.app import app, db

from models import Election, Authority, QueryQueue
from create_election.performer_jobs import check_election_data


from taskqueue import queue_task, apply_task, dequeue_task

public_api = Blueprint('public_api', __name__)

def error(status, message=""):
    if message:
        data = json.dumps(dict(message=message))
    else:
        data=""
    return make_response(data, status)


@public_api.route('/dequeue', methods=['GET'])
def dequeue():
    try:
        dequeue_task()
    except Exception as e:
        return make_response(dumps(dict(status=e.message)), 202)

    return make_response(dumps(dict(status="ok")), 202)


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
    d = base64.b64encode(pickle.dumps(data)).decode('utf-8')
    queueid = queue_task(task='election', data=d)

    return make_response(dumps(dict(queue_id=queueid)), 202)


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
    d = base64.b64encode(pickle.dumps(data)).decode('utf-8')
    queueid = queue_task(task='tally', data=d)
    return make_response(dumps(dict(queue_id=queueid)), 202)

@public_api.route('/receive_election', methods=['POST'])
def receive_election():
    '''
    This is a test route to be able to test that callbacks are correctly sent
    '''
    print("ATTENTION received election callback: ")
    print(request.get_json(force=True, silent=True))
    return make_response("", 202)


@public_api.route('/receive_tally', methods=['POST'])
def receive_tally():
    '''
    This is a test route to be able to test that callbacks are correctly sent
    '''
    print("ATTENTION received tally callback: ")
    print(request.get_json(force=True, silent=True))
    return make_response("", 202)
