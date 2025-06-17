# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import re
import os
import codecs
import subprocess
import json
import shutil
import signal
from datetime import datetime

from frestq import decorators
from frestq.utils import dumps, loads
from frestq.tasks import SimpleTask, ParallelTask, ExternalTask, TaskError
from frestq.protocol import certs_differ
from frestq.app import app, db

import shutil
from models import Election, Authority, Session
from utils import *
from vmn import *

@decorators.task(action="delete_private_info", queue="orchestra_performer")
def generate_private_info(task):
    '''
    Deletes the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    election_id = input_data['id']

    # Delete the folder and all its contents
    try:
        delete_election_folders(election_id)
        print(f"Successfully deleted election: {election_id}")
    except FileNotFoundError:
        print(f"Folder not found: {election_id}")
    except PermissionError:
        print(f"Permission denied: {election_id}")
    except Exception as e:
        print(f"Error deleting folder {election_id}: {e}")


def delete_election_folders(election_id):
    # check election exists
    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    if not election:
        raise TaskError(dict(reason="election not created"))
    
    remove_existing_election(election_id)

    # each session is a question
    sessions = election.sessions.all()
    for session in sessions:
        ballots = session.ballots
        for ballot in ballots:
            db.session.delete(ballot)
    
    db.session.delete(election)
    db.session.commit()

def remove_existing_election(election_id):
    tally_path = get_public_dir_path(election_id)
    priv_tally_path = get_private_dir_path(election_id)

    if os.path.exists(tally_path):
        print(f"removing {tally_path}")
        os.remove(tally_path)

    if os.path.exists(priv_tally_path):
        print(f"removing {priv_tally_path}")
        os.remove(priv_tally_path)

def get_public_dir_path(election_id):
    pubdata_path = app.config.get('PUBLIC_DATA_PATH', '')
    election_pubpath = os.path.join(pubdata_path, str(election_id))
    return election_pubpath

def get_private_dir_path(election_id):
    privdata_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(privdata_path, str(election_id))
    return election_privpath