#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-FileCopyrightText: 2013-2023 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#

import logging
import os
import sys

from frestq.app import app, DefaultConfig as FrestqDefaultConfig

from .models import *
from .tally_election import performer_jobs
from .public_api import public_api
from .taskqueue import start_queue


class DefaultConfig(FrestqDefaultConfig):
    # debug, set to false on production deployment
    DEBUG = True

    # see https://stackoverflow.com/questions/33738467/how-do-i-know-if-i-can-disable-sqlalchemy-track-modifications/33790196#33790196
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # URL to our HTTP server
    VFORK_SERVER_URL = 'http://127.0.0.1'

    VFORK_SERVER_PORT = "8082"

    # Socket address given as <hostname>:<port> to our hint server.
    # A hint server is a simple UDP server that reduces latency and
    # traffic on the HTTP servers.
    VFORK_HINT_SERVER_SOCKET = '127.0.0.1'

    VFORK_HINT_SERVER_PORT = "8084"

    ROOT_PATH = os.path.split(os.path.abspath(__file__))[0]

    SQLALCHEMY_DATABASE_URI = 'sqlite:///%s/db.sqlite' % ROOT_PATH

    PRIVATE_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/private')
    PUBLIC_DATA_PATH = os.path.join(ROOT_PATH, 'datastore/public')


def extra_parse_args(self, parser):
    parser.add_argument(
        "--reset-tally",
        help="Enable making a second tally for :election_id",
        type=int
    )

def extra_run(self):
    if self.pargs.reset_tally and isinstance(self.pargs.reset_tally, int):
        election_id = self.pargs.reset_tally
        performer_jobs.reset_tally(election_id)
        return True

    return False

def configure_app(app):
    '''
    override config from environment variables, using defaults from the class
    DefaultConfig.
    '''
    config_object = DefaultConfig()
    config_var_prefix = "EO_"
    for variable, value in os.environ.items():
        if variable.startswith(config_var_prefix):
            env_name = variable.split(config_var_prefix)[1]
            logging.debug(f"SET:from-env-var config.{env_name} = {value}")
            setattr(config_object, env_name, value)
    app.configure_app(scheduler=False, config_object=config_object)
    app.register_blueprint(public_api, url_prefix='/public_api')

configure_app(app)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "create-tarball":
        from tools import create_tarball
        create_tarball.create(sys.argv[2])
        exit(0)
    app.run(
        parse_args=True,
        extra_parse_func=extra_parse_args, 
        extra_run=extra_run
    )
else:
    # used when run using uwsgi or similar
    with app.app_context():
        start_queue()
