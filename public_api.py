# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
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
          "orchestra_url": "https://sequentech.io:6874/orchestra",
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

@public_api.route('/download_private_share', methods=['POST'])
def download_private_share():
    '''
    Download private share of the keys
    '''
    print("ATTENTION received download-private-share: ")
    import tempfile
    from utils import parse_json_request
    from models import Session
    from frestq.app import db
    from flask import send_file
    import os
    import shutil
    from tools.create_tarball import hash_file, create_deterministic_tar_file

    data = request.get_json(force=True, silent=True)
    req = parse_json_request(request)
    election_id = req.get('election_id', None)

    if election_id is None:
        make_response("election id missing", 400)

    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()

    session_ids = [s.id for s in db.session.query(Session).\
            with_parent(election,"sessions").\
            order_by(Session.question_number)]

    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, str(election_id))

    with tempfile.TemporaryDirectory() as tmpdirname:
        for session in session_ids:
            session_privpath = os.path.join(election_private_path, session.id, 'privInfo.xml')
            if not os.path.exists(session_privpath):
                return make_response(f'missing file {session_privpath}', 500)

            # hash session file
            session_privpath_hashfile = os.path.join(election_private_path, session.id, 'privInfo.xml.sha256')
            session_privpath_hash = hash_file(session_privpath)
            if os.path.exists(session_privpath_hashfile):
                # check the sha256 of the private key
                with open("contents.txt", "r", encoding = 'utf-8') as hash_file:
                    hash_text = hash_file.read()
                    if hash_text != session_privpath_hash:
                        return make_response(f'hash for private key file {session_privpath} error: {hash_text} != {session_privpath_hash}', 500)
            else:
                # write the sha256 of the private key
                with open(session_privpath_hashfile, 'w', encoding = 'utf-8') as hash_file:
                    hash_file.write(session_privpath_hash)

            os.mkdir(os.path.join(tmpdirname, session.id), 0o755)
            copy_privpath = os.path.join(tmpdirname, session.id, 'privInfo.xml')
            shutil.copyfile(session_privpath, copy_privpath)
        
        # create and return tar file
        with tempfile.TemporaryDirectory() as tmp_tar_folder:
            tar_filename = "private_keys.tar.gz"
            tar_file_path = os.path.join(tmp_tar_folder, tar_filename)
            create_deterministic_tar_file(tmp_tar_folder, tmpdirname)

            response = send_file(tar_file_path, as_attachment=True, attachment_filename=tar_filename,
                         add_etags=False, mimetype="application/gzip")
            
            response.headers.extend({
                'Content-Length': os.path.getsize(tar_file_path),
                'Cache-Control': 'no-cache'
            })

    return response
