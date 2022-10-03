from frestq.app import app, db
from models import Election
import tempfile
from models import Session
import os
import shutil
from tools.create_tarball import hash_file, create_deterministic_tar_file
from flask import request, make_response

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

def create_file_hash(file_path):
    hashed_file_path = get_file_hash_path(file_path)
    hash_text = hash_file(file_path, encoding = 'utf-8')
    
    # write the sha256 of the private key
    with open(hashed_file_path, 'w', encoding = 'utf-8') as hashed_file:
        hashed_file.write(hash_text)

def check_file_hash(file_path):
    hashed_file_path = get_file_hash_path(file_path)
    hash_text = hash_file(file_path, encoding = 'utf-8')

    with open(hashed_file_path, "r", encoding = 'utf-8') as hashed_file:
        existing_hash_text = hashed_file.read()
        return existing_hash_text == hash_text

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
            return tar_file_path

def download_private_share(election_id):
    '''
    Download private share of the keys
    '''

    if election_id is None:
        return ("election id missing", 400)

    election = get_election_by_id(election_id)

    session_ids = get_election_session_ids(election)
    private_key_file_paths = [get_session_private_key_path(election_id, session_id) for session_id in session_ids]

    # assert private key file  hashes
    for session_privpath in private_key_file_paths:
        if not os.path.exists(session_privpath):
            return (f'missing file {session_privpath}', 500)

        # hash session file
        session_privpath_hashfile = get_file_hash_path(session_privpath)
        if os.path.exists(session_privpath_hashfile):
            if not check_file_hash(session_privpath_hashfile):
                    return (f'hash for private key file error', 500)
        else:
            # write the sha256 of the private key
            create_file_hash(session_privpath_hashfile)
    
    # create tar file with private keys
    tar_file_path = create_tar_for_private_keys(create_tar_for_private_keys(election_id, session_ids))

    return (tar_file_path, 200)