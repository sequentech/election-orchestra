#
# SPDX-FileCopyrightText: 2024 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
from frestq.tasks import SimpleTask
from frestq.app import app, db

def send_delete_election_task(election_id):
    task = SimpleTask(
        receiver_url=app.config.get('ROOT_URL', ''),
        action="delete_election",
        queue="launch_task",
        data={
            'election_id': election_id,
        }
    )
    task.create_and_send()