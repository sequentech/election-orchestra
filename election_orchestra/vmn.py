#
# SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
import subprocess
from .utils import *
from frestq.app import app

#
# interface functions for mixnet commands
#

def kill_mixnet():
    print("killing previous mixnet instances..")
    devnull = open('/dev/null', 'w')
    subprocess.call("ps aux | grep java | grep -i mixnet | awk '{print $2}' | xargs kill -9",
      shell=True, stdout=devnull, stderr=devnull)

def pre_kill_mixnet(func):
    def go(*args, **kwargs):
        # TODO: add some config flag
        if(app.config.get('KILL_ALL_VFORK_BEFORE_START_NEW', False)):
            kill_mixnet()

        return func(*args, **kwargs)
    return go

@pre_kill_mixnet
def v_gen_protocol_info(session_id, name, num_parties, num_threshold_parties, session_privpath):
    command = ["vmni", "-prot", "-sid", session_id, "-name", name, "-nopart",
        str(num_parties), "-thres", str(num_threshold_parties)]

    return subprocess.check_call(command, cwd=session_privpath)

@pre_kill_mixnet
def v_gen_private_info(auth_name, server_url, hint_server_url, session_privpath):
    command = ["vmni", "-party", "-arrays", "file", "-name", auth_name, "-http",
            server_url, "-hint", hint_server_url]

    return subprocess.check_call(command, cwd=session_privpath)

@pre_kill_mixnet
def v_merge(protinfos, session_privpath):
    start = ["vmni", "-merge"]
    command = start + protinfos

    return subprocess.check_call(command, cwd=session_privpath)

@pre_kill_mixnet
def v_gen_public_key(session_privpath, output_filter):
    return call_cmd(["vmn", "-keygen", "publicKey_raw"], cwd=session_privpath,
             timeout=10*60, check_ret=0, output_filter=output_filter)

@pre_kill_mixnet
def v_mix(session_privpath, output_filter=None):
    return call_cmd(["vmn", "-mix", "privInfo.xml", "protInfo.xml",
        "ciphertexts_raw", "plaintexts_raw"], cwd=session_privpath,
        timeout=5*3600, check_ret=0, output_filter=output_filter)

@pre_kill_mixnet
def v_reset(election_private_path):
    return subprocess.check_call(["vmn", "-reset", "privInfo.xml", "protInfo.xml",
      "-f"], cwd=election_private_path)

def v_verify(protinfo_path, proofs_path):
    return subprocess.check_output(["vmnv", protinfo_path, proofs_path, "-v"])

def v_convert_pkey_json(session_privpath, output_filter):
  return call_cmd(["vmnc", "-pkey", "-outi", "json", "publicKey_raw",
    "publicKey_json"], cwd=session_privpath, timeout=20, check_ret=0,
    output_filter=output_filter)

def v_convert_ctexts_json(session_privpath):
    return subprocess.check_call(["vmnc", "-ciphs", "-ini", "json",
            "ciphertexts_json", "ciphertexts_raw"], cwd=session_privpath)

def v_convert_plaintexts_json(session_privpath):
    return call_cmd(["vmnc", "-plain", "-outi", "json", "plaintexts_raw",
        "plaintexts_json"], cwd=session_privpath, check_ret=0, timeout=3600)
