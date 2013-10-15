#!/usr/bin/env python
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

import sys
import os
import json
import subprocess

import sha512

NUM_DEMO_CIPHS = 100
VOTES_FILENAME = 'votes'
BASE_URL = 'https://127.0.0.1:5000'

def rm_if_exists(path):
    if os.path.exists(path):
        os.unlink(path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "usage: %s <path>\n"\
            "Where path is a directory containing the public election\n" % sys.argv[0]
        exit(1)

    path = sys.argv[1]

    if not os.path.exists(sys.argv[1]):
        print "path = %s\n does not exist" % sys.argv[1]

    # go across each subdir, which we assume represents a session-id, and create
    # demo encrypted texts
    i = 0
    vote_paths = []
    for item in os.listdir(path):
        sessionpath = os.path.join(path, item)
        if not os.path.isdir(sessionpath):
            continue

        votespath = os.path.join(path, VOTES_FILENAME + str(i))
        vote_paths.append(votespath)
        rm_if_exists(votespath)

        l = ["vmnd", "-i", "json", "protInfo.xml", "publicKey_json",
            str(NUM_DEMO_CIPHS), votespath]
        subprocess.check_call(l, cwd=sessionpath)
        i += 1

    # now we unify the votes, writting them altogether in one file, in the
    # following format, each line will represent one vote
    # {"choices": [vote_for_session1, vote_for_session2, [...]], "proofs": []}
    votes_path = os.path.join(path, VOTES_FILENAME)
    rm_if_exists(votes_path)
    f = open(votes_path, 'w')
    fvps = []
    for votepath in vote_paths:
        fvps.append(open(votepath, 'r'))

    for i in xrange(NUM_DEMO_CIPHS):
        choices = []
        for fi in fvps:
            choices.append(json.loads(fi.readline()))

        ballot = dict(choices=choices, proofs=[])
        f.write(json.dumps(ballot))
        f.write("\n")

    # close all files
    f.close()
    for fi in fvps:
        fi.close()

    votes_url = "%s/public_data/%s/%s" % (BASE_URL, os.path.basename(path),
        VOTES_FILENAME)
    sha512_hash = sha512.hash_file(votes_path)

    # print results
    print json.dumps({
        "election_id": os.path.basename(path),
        "callback_url": "%s/public_api/receive_tally" % BASE_URL,
        "extra": [],
        "votes_url": votes_url,
        "votes_hash": "sha512://%s" % sha512_hash
    }, indent=4)
    print "\n"