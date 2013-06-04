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

api = Blueprint('api', __name__)

def error(status, message=""):
    if message:
        data = json.dumps(dict(message=message))
    else:
        data=""
    return make_response(data, status)

@api.route('/election', methods=['POST'])
def post_election():
    '''
    POST /election

    Creates an election, with the given input data. This involves communicating
    with the different election authorities to generate the joint public key.

    Example request:
    POST /election
    {
        "session_id": "d9e5ee09-03fa-4890-aa83-2fc558e645b5",
        "title": "New Directive Board",
        "is_recurring": false,
        "callback_url": "http://example.com/callback_create_election",
        "extra": [],
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
    from models import Election
    from app import db
    try:
        data = json.loads(request.data)
    except:
        return error(400, "invalid json")

    # check input data
    requirements = [
        {'name': 'session_id', 'isinstance': basestring},
        {'name': 'title', 'isinstance': basestring},
        {'name': 'is_recurring', 'isinstance': bool},
        {'name': 'callback_url', 'isinstance': basestring},
        {'name': 'extra', 'isinstance': list},
        {'name': 'authorities', 'isinstance': list},
    ]
    for req in requirements:
        if req['name'] not in data or not isinstance(data[req['name']],
            req['isinstance']):
            return error(400, "invalid %s parameter" % req['name'])

    if len(data['authorities']) == 0:
        return error(400, 'no authorities')

    q = Election.query.filter_by(session_id=data['session_id'])
    if len(q.all()) > 0:
        return error(400, 'an election with session id %s already '
            'exists' % data['session_id'])

    e = Election(
        session_id = data['session_id'],
        title = data['title'],
        is_recurring = data['is_recurring'],
        callback_url = data['callback_url']
    )
    db.session.add(e)
    db.session.commit()

    return make_response('', 202)
