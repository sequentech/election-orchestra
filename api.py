# -*- coding: utf-8 -*-

from __future__ import absolute_import
from flask import Blueprint, request, make_response

app = Blueprint('api', __name__)


@app.route('/election', methods=['POST'])
def post_election():
    return 'hello world!'
