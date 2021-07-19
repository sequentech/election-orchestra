# This file is part of election-orchestra.
# Copyright (C) 2021  Agora Voting SL <contact@nvotes.com>

# authapi is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License.

# authapi  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with authapi.  If not, see <http://www.gnu.org/licenses/>.
from setuptools import setup

setup(
    name='election-orchestra',
    version='20.01',
    author='nVotes Team',
    author_email='contact@nvotes.com',
    packages=['frestq'],
    scripts=[],
    url='http://pypi.python.org/pypi/election-orchestra/',
    license='AGPL-3.0',
    description='election orchestrator',
    long_description=open('README.md').read(),
    install_requires=[
        'frestq @ git+https://github.com/agoravoting/frestq.git@review-deps-licenses',
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
        'ipython==7.17.0',
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
