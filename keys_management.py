from frestq.app import app, db
from models import Election
import tempfile
from models import Session
import os
import shutil
from tools.create_tarball import hash_file, hash_bytes, create_deterministic_tar_file, extract_tar_file
from flask import request, make_response
import base64

def get_election_by_id(election_id):
    return db.session.query(Election)\
        .filter(Election.id == election_id).first()

def get_election_session_ids(election):
    return [s.id for s in db.session.query(Session).\
            with_parent(election,"sessions").\
            order_by(Session.question_number)]

def get_session_private_key_path(election_id, session_id):
    private_data_path = app.config.get('PRIVATE_DATA_PATH', '')
    election_private_path = os.path.join(private_data_path, str(election_id))
    return os.path.join(election_private_path, session_id, 'privInfo.xml')

def get_file_hash_path(file_path):
    return file_path + '.sha256'

def write_text_file(file_path, text):
    # write the sha256 of the private key
    with open(file_path, 'w', encoding = 'utf-8') as file:
        file.write(text)

def read_text_file(file_path):
    with open(file_path, "r", encoding = 'utf-8') as file:
        return file.read()

def read_binary_file(file_path):
    with open(file_path, "rb") as f:
        return f.read()

def write_binary_file(file_path, bytes):
    # write the sha256 of the private key
    with open(file_path, 'wb') as file:
        file.write(bytes)

def create_tar_for_private_keys(election_id, session_ids):
    with tempfile.TemporaryDirectory() as tmpdirname:
        for session_id in session_ids:
            session_privpath = get_session_private_key_path(election_id, session_id)
            os.mkdir(os.path.join(tmpdirname, session_id), 0o755)
            copy_privpath = os.path.join(tmpdirname, session_id, 'privInfo.xml')
            shutil.copyfile(session_privpath, copy_privpath)
        
        # create and return tar file
        with tempfile.TemporaryDirectory() as tmp_tar_folder:
            tar_filename = "private_keys.tar.gz"
            tar_file_path = os.path.join(tmp_tar_folder, tar_filename)
            create_deterministic_tar_file(tar_file_path, tmpdirname)
            #return base64_encode_file(tar_file_path)
            return read_binary_file(tar_file_path)

def assert_private_key_file_hashes(election_id, session_ids):
    private_key_file_paths = [get_session_private_key_path(election_id, session_id) for session_id in session_ids]

    # assert private key file  hashes
    for session_privpath in private_key_file_paths:
        if not os.path.exists(session_privpath):
            return (f'missing file {session_privpath}', 500)

        # hash session file
        session_privpath_hashfile = get_file_hash_path(session_privpath)

        hashed_file_path = get_file_hash_path(session_privpath)
        hash_text = hash_file(session_privpath, mode = 'rb')
        if os.path.exists(session_privpath_hashfile):
            existing_hash_text = read_text_file(hashed_file_path)
            if existing_hash_text != hash_text:
                    return (f'private key file has a hash consistency error', 500)
        else:
            # write the sha256 of the private key
            write_text_file(hashed_file_path, hash_text)
    
    return (None, 200)

def download_private_share(election_id):
    '''
    Download private share of the keys
    '''
    election = get_election_by_id(election_id)
    session_ids = get_election_session_ids(election)

    msg, code = assert_private_key_file_hashes(election_id, session_ids)
    if code != 200:
        return (msg, code)

    # create tar file with private keys
    tar_file_bytes = create_tar_for_private_keys(election_id, session_ids)
    tar_file_b64 = base64.b64encode(tar_file_bytes)

    return (tar_file_b64, 200)

def check_private_share(election_id, private_key_base64):
    '''
    Check provided private key against database
    '''
    private_key_bytes = base64.b64decode(private_key_base64)

    election = get_election_by_id(election_id)
    session_ids = get_election_session_ids(election)

    msg, code = assert_private_key_file_hashes(election_id, session_ids)
    if code != 200:
        return (msg, code)

    pk_hash = hash_bytes(private_key_bytes)

    tar_file_bytes = create_tar_for_private_keys(election_id, session_ids)
    tar_hash = hash_bytes(tar_file_bytes)
    
    return (str(tar_hash == pk_hash), 200)

def delete_private_share(election_id, private_key_base64):
    '''
    Delete private share of keys
    '''
    # first check hashes
    msg, code = check_private_share(election_id, private_key_base64)
    if code != 200:
        return (msg, code)
    
    # if everything is okay, continue to delete
    election = get_election_by_id(election_id)
    session_ids = get_election_session_ids(election)
    private_key_file_paths = [get_session_private_key_path(election_id, session_id) for session_id in session_ids]

    # ensure all files exist or otherwise delete none
    for session_privpath in private_key_file_paths:
        if not os.path.exists(session_privpath):
            return (f'missing file {session_privpath}', 500)

    for session_privpath in private_key_file_paths:
        os.remove(session_privpath)
    
    return ("", 200)

def restore_private_share(election_id, private_key_base64):
    private_key_bytes = base64.b64decode(private_key_base64)

    election = get_election_by_id(election_id)
    session_ids = get_election_session_ids(election)

    with tempfile.NamedTemporaryFile() as tar_file:
        tar_file_path = tar_file.name
        write_binary_file(tar_file_path, private_key_bytes)

        with tempfile.TemporaryDirectory() as target_extract_folder:
            extract_tar_file(tar_file_path, target_extract_folder)

            for session_id in session_ids:
                private_key_file_path = get_session_private_key_path(election_id, session_id)
                private_key_file_hash_path = get_file_hash_path(private_key_file_path)
                tar_key_file_path = os.path.join(target_extract_folder, session_id, 'privInfo.xml')

                if not os.path.exists(tar_key_file_path):
                    return (f'Missing key in tar file for session id {session_id}', 400)

                if not os.path.exists(private_key_file_hash_path):
                    return (f'Missing hash for key share in session id {session_id}', 500)
                
                existing_hash_text = read_text_file(private_key_file_hash_path)
                
                if os.path.exists(private_key_file_path):
                    hash_text = hash_file(private_key_file_path, mode = 'rb')
                    if existing_hash_text != hash_text:
                        return ('private key file has a hash consistency error', 500)

                tar_key_file_hash = hash_file(tar_key_file_path, mode = 'rb')

                # check hashes match
                if tar_key_file_hash != existing_hash_text:
                    return (f'hashes don\'t match for session id {session_id}', 400)
                
                # copy share of key for session id
                shutil.copyfile(tar_key_file_path, private_key_file_path)

    return ("", 200)

