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

    election = db.session.query(Election)\
        .filter(Election.id == election_id).first()
    
    db.session.delete(election)
    db.session.commit()

    # 1. check this is a new election and check input data
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_privpath = os.path.join(private_data_path, str(election_id))

    # Delete the folder and all its contents
    try:
        shutil.rmtree(election_privpath)
        print(f"Successfully deleted private data folder: {election_privpath}")
    except FileNotFoundError:
        print(f"Folder not found: {election_privpath}")
    except PermissionError:
        print(f"Permission denied: {election_privpath}")
    except Exception as e:
        print(f"Error deleting folder {election_privpath}: {e}")
