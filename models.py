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
from datetime import datetime

from flask import Flask, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, VARCHAR

from frestq.app import db

class Election(db.Model):
    '''
    Represents an election
    '''
    session_id = db.Column(db.Unicode(255), primary_key=True)

    is_recurring = db.Column(db.Boolean)

    num_parties = db.Column(db.Integer)

    threshold_parties = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    title = db.Column(db.Unicode(255))

    url = db.Column(db.Unicode(1024))

    description = db.Column(db.UnicodeText)

    # converted into and from JSON
    question_data = db.Column(db.UnicodeText)

    voting_start_date = db.Column(db.DateTime)

    voting_end_date = db.Column(db.DateTime)

    status = db.Column(db.Unicode(128))

    callback_url = db.Column(db.Unicode(1024))

    public_key = db.Column(db.UnicodeText)

    protinfo_filepath = db.Column(db.Unicode(1024))

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<Election %r>' % self.title

    def to_dict(self, full=False):
        '''
        Return an individual instance as a dictionary.
        '''
        ret = {
            'title': self.title,
            'session_id': self.session_id,
            'is_recurring': self.is_recurring,
            'num_parties': self.num_parties,
            'threshold_parties': self.threshold_parties,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at,
            'status': self.status,
            'public_key': self.public_key,
            #'protinfo_filepath': self.protinfo_filepath, TODO
            'callback_url': self.callback_url
        }

        if full:
            ret['authorities'] = [a.to_dict() for a in self.authorities]

        return ret


class Authority(db.Model):
    '''
    Represents an authority
    '''

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.Unicode(255))

    ssl_cert = db.Column(db.UnicodeText)

    orchestra_url = db.Column(db.Unicode(1024))

    session_id = db.Column(db.Unicode(255), db.ForeignKey('election.session_id'))

    election = db.relationship('Election',
        backref=db.backref('authorities', lazy='dynamic'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<Authority %r>' % self.name

    def to_dict(self):
        '''
        Return an individual instance as a dictionary.
        '''
        return {
            'id': self.id,
            'name': self.name,
            'ssl_cert': self.ssl_cert,
            'orchestra_url': self.orchestra_url,
            'session_id': self.session_id
        }


class AuthoritySession(db.Model):
    '''
    Represent the information related to an authority in a tally
    '''
    id = db.Column(db.Integer, primary_key=True)

    authority_id = db.Column(db.Integer, db.ForeignKey('authority.id'))

    status = db.Column(db.Unicode(128))

    authority = db.relationship('Authority',
        backref=db.backref('sessions', lazy='dynamic'))

    tally_id = db.Column(db.Integer, db.ForeignKey('tally.id'))

    tally = db.relationship('Tally',
        backref=db.backref('authority_sessions', lazy='dynamic'))

    verificatum_server_url = db.Column(db.Unicode(1024))

    verificatum_hint_server_url = db.Column(db.Unicode(1024))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    session_expirates_at = db.Column(db.DateTime)

    tally_filepath = db.Column(db.Unicode(1024))

    def __repr__(self):
        return '<AuthoritySession %r>' % self.authority.name


class Tally(db.Model):
    '''
    Represents an authority's tally
    '''

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.Unicode(255))

    status = db.Column(db.Unicode(128))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    votes_url = db.Column(db.Unicode(1024))

    votes_filepath = db.Column(db.Unicode(1024))

    tally_filepath = db.Column(db.Unicode(1024))

    def __repr__(self):
        return '<Authority %r>' % self.name

    def to_dict(self):
        '''
        Return an individual instance as a dictionary.
        '''
        return {
            'id': self.id,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at,
            'status': self.status,
            'election_id': self.election_id,
            'votes_url': self.election_id,
            #'votes_filepath': self.votes_filepath,
            #'tally_filepath': self.tally_filepath,
        }

class Vote(db.Model):
    '''
    Represents a vote. This is used to forbid tallying the same vote twice if
    the election is not recurring.
    '''
    id = db.Column(db.Integer, primary_key=True)

    vote_hash = db.Column(db.Unicode(1024))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session_id = db.Column(db.Unicode(255), db.ForeignKey('election.session_id'))

    election = db.relationship('Election',
        backref=db.backref('votes', lazy='dynamic'))

    def __repr__(self):
        return '<Vote %r>' % self.vote_hash
