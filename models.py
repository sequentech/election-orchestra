# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Agora Voting SL <contact@nvotes.com>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import json
from datetime import datetime

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, VARCHAR

from frestq.app import db

class Election(db.Model):
    '''
    Represents an election, with multiple possible questions, each of them
    will be tallied separatedly with its own session (and its own pubkey).
    '''
    id = db.Column(db.BigInteger, primary_key=True)

    num_parties = db.Column(db.Integer)

    threshold_parties = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    title = db.Column(db.Unicode(255))


    description = db.Column(db.UnicodeText)

    # converted into and from JSON
    questions = db.Column(db.UnicodeText)

    start_date = db.Column(db.DateTime)

    end_date = db.Column(db.DateTime)

    status = db.Column(db.Unicode(128))

    callback_url = db.Column(db.Unicode(1024))

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<Election %r>' % self.title

    def to_dict(self, full=False):
        '''
        Return an individual instance as a dictionary.
        '''
        ret = {
            'title': self.title,
            'id': self.id,
            'num_parties': self.num_parties,
            'threshold_parties': self.threshold_parties,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at,
            'status': self.status,
            'callback_url': self.callback_url
        }

        if full:
            ret['authorities'] = [a.to_dict() for a in self.authorities]

        return ret


class Session(db.Model):
    '''
    Refers vfork session, with its own public key and protinfo
    '''
    id = db.Column(db.Unicode(255), primary_key=True)

    election_id = db.Column(db.Integer, db.ForeignKey('election.id'))

    question_number = db.Column(db.Integer)

    election = db.relationship('Election',
        backref=db.backref('sessions', lazy='dynamic', order_by=question_number))

    status = db.Column(db.Unicode(128))

    public_key = db.Column(db.UnicodeText)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<Session %r>' % self.title

    def to_dict(self, full=False):
        '''
        Return an individual instance as a dictionary.
        '''
        return {
            'id': self.id,
            'election_id': self.election_id,
            'status': self.status,
            'public_key': self.public_key,
            'question_number': self.question_number
        }


class Authority(db.Model):
    '''
    Represents an authority
    '''

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.Unicode(255))

    ssl_cert = db.Column(db.UnicodeText)

    orchestra_url = db.Column(db.Unicode(1024))

    election_id = db.Column(db.Integer, db.ForeignKey('election.id'))

    election = db.relationship('Election',
        backref=db.backref('authorities', lazy='dynamic'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
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
            'election_id': self.election_id
        }


class Ballot(db.Model):
    session_id = db.Column(db.Unicode(255), db.ForeignKey('session.id'), primary_key=True)

    ballot_hash = db.Column(db.Unicode(45), primary_key=True)

    session = db.relationship('Session',
        backref=db.backref('ballots', lazy='dynamic'))

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return '<Ballot %r>' % self.ballot_hash

    def to_dict(self):
        '''
        Return an individual instance as a dictionary.
        '''
        return {
            'session_id': self.session_id,
            'ballot_hash': self.ballot_hash
        }


class QueryQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task = db.Column(db.Unicode(20))
    data = db.Column(db.UnicodeText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doing = db.Column(db.Boolean, default=False)
