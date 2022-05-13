#
# SPDX-FileCopyrightText: 2013-2021 Agora Voting SL <contact@nvotes.com>
#
# SPDX-License-Identifier: AGPL-3.0-only
#
from setuptools import setup, find_packages

setup(
    name='election-orchestra',
    version='5.1.1',
    author='nVotes Team',
    author_email='contact@nvotes.com',
    packages=find_packages(),
    scripts=[],
    url='http://github.com/agoravoting/election-orchestra',
    license='AGPL-3.0',
    description='election orchestrator',
    long_description=open('README.md').read(),
    install_requires=[
        'frestq @ git+https://github.com/agoravoting/frestq.git@5.1.1',
        'requests==2.22.0',
        'Flask==1.0.0',
        'Flask-SQLAlchemy==2.4.4',
        'Jinja2==2.11.3',
        'MarkupSafe==0.23',
        'SQLAlchemy==1.3.23',
        'Werkzeug==1.0.1',
        'argparse==1.2.1',
        'cffi==1.14.4',
        'cryptography==3.3.2',
        'pyOpenSSL==18.0.0',
        'ipdb==0.13.9',
        'ipython==7.31.1',
        'itsdangerous==0.24',
        'prettytable==0.7.2',
        'psycopg2-binary==2.8.6',
        'pycparser==2.10',
        'uwsgi==2.0.18',

    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "OSI Approved :: GNU Affero General Public License v3"
    ],
    python_requires='>=3.5',
    dependency_links = []
)
