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
from delete_election.performer_jobs import reset_tally

@decorators.task(action="delete_private_info", queue="orchestra_performer")
def generate_private_info(task):
    '''
    Deletes the local private info for a new election
    '''
    input_data = task.get_data()['input_data']
    election_id = input_data['id']

    # Delete the folder and all its contents
    try:
        reset_tally(election_id, True)
        print(f"Successfully deleted election: {election_id}")
    except FileNotFoundError:
        print(f"Folder not found: {election_id}")
    except PermissionError:
        print(f"Permission denied: {election_id}")
    except Exception as e:
        print(f"Error deleting folder {election_id}: {e}")
