Election Orchestra
==================

This software orchestrates the authorities servers to create election
public-keys and perform the tallying using verificatum.

Installation
============

1. Download from the git repository if you haven't got a copy

```
    $ git clone https://github.com/agoraciudadana/election-orchestra && cd election-orchestra
```

2. Install package and its dependencies

```
    $ mkvirtualenv myenv
    $ pip install -r requirements.txt
    $ sudo python setup.py install
```

Configuration
=============

You'll need to generate your own ssl certificate, then configure your favourite
web server to be used as the frestq frontend. Also you need to create a database
and configure everythin in your a settings.py file. Then do something like the
following to initialize the database:

```
    $ FRESTQ_SETTINGS=settings.py python app.py --createdb
```

Then launch in a similar way to this (take a look at auth1.ini):

```
    $ uwsgi --ini auth.ini
```

To generate a self-signed certificate you can do:


```
    $ openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 1000 -nodes
```

You can find an example nginx configuration in https://github.com/agoraciudadana/frestq/blob/master/examples/hellossl/nginx_hellossl.conf

Tutorial
========

For everyday use, you just need to every once and again take a look at what new
elections or tallies have been requested, review them, and accept or deny them.

To list pding external tasks, execute the following command:

```
    $ FRESTQ_SETTINGS=settings.py ./app.py --tasks --filters "task_type=external" "status=executing" 2>/dev/null

    +----------+-----------------------------------+---------------------------+-----------------+-----------+-----------+----------------------------+
    | small id |             sender_url            |           action          |      queue      | task_type |   status  |        created_date        |
    +----------+-----------------------------------+---------------------------+-----------------+-----------+-----------+----------------------------+
    | 86ba85d2 | https://127.0.0.1:5000/api/queues | frestq.virtual_empty_task | internal.frestq |  external | executing | 2013-09-29 11:55:09.424713 |
    | 76df2601 | https://127.0.0.1:5000/api/queues | frestq.virtual_empty_task | internal.frestq |  external | executing | 2013-09-29 11:27:59.563677 |
    +----------+-----------------------------------+---------------------------+-----------------+-----------+-----------+----------------------------+

```

To show the details of a specific external task, execute:

```
    $ FRESTQ_SETTINGS=settings.py python app.py --show-external <shortid> 2>/dev/null
    * frestq.virtual_empty_task.internal.frestq - external (86ba85d2, finished)
    label: approve_election
    info_text:
    * URL: https://example.com/election/url
    * Title: New Directive Board
    * Description: election description
    * Voting period: 2013-12-06T18:17:14.457000 - 2013-12-09T18:17:14.457000
    * Question data: {
        "max": 1,
        "min": 0,
        "question": "Who Should be President?",
        "answers": [
            "Alice",
            "Bob"
        ],
        "tally_type": "ONE_CHOICE"
    }
    * Authorities: [
        {
            "session_id": "vota4",
            "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIDwTCCAqmgAwIBAgIJAJjjgNzBed6aMA0GCSqGSIb3DQEBBQUAMHcxCzAJBgNV\nBAYTAkVTMQ8wDQYDVQQIDAZNYWRyaWQxDzANBgNVBAcMBk1hZHJpZDETMBEGA1UE\nCgwKVGVzdCBBZ29yYTEPMA0GA1UEAwwGRlJFU1RRMSAwHgYJKoZIhvcNAQkBFhFl\nZHVsaXhAd2Fkb2JvLmNvbTAeFw0xMzA3MjIxNjA2NTdaFw0xNjA1MTExNjA2NTda\nMHcxCzAJBgNVBAYTAkVTMQ8wDQYDVQQIDAZNYWRyaWQxDzANBgNVBAcMBk1hZHJp\nZDETMBEGA1UECgwKVGVzdCBBZ29yYTEPMA0GA1UEAwwGRlJFU1RRMSAwHgYJKoZI\nhvcNAQkBFhFlZHVsaXhAd2Fkb2JvLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEP\nADCCAQoCggEBAMLzkBGTwH7FiA36SyjlmlV8kh+jZ//LP4PqJNJjc5SAJHGxbexI\nI2lzEFQbHMXBbHPM1NnLJitv0y8Gg9QWWBajqQeymu8O0Np7u1LG9JqNzRKIEDXk\n0SZgSoCld/cCTvtUgcT68CBE55af5EifjCI4fRf2229AiP7iibVsQ5dL/zyxLnEe\nGvuSrd+s8xyVp3pyhfHAlRe+ftATjJ3wBUGCmUr9d1lS9fQziCIYzeq9fWnwxCz/\ngp76930iUEIp7vYQzSfgbWSuQgrlrZUOIR/2+Rfk2Y1S6dE9NwjGtLp3kMOIeM9A\nclA/YyPUR47DX2yHxjIUz7jLT+li5Wrx7JUCAwEAAaNQME4wHQYDVR0OBBYEFOuX\nWa3ax+1lokcIZ39dvOp5tyzUMB8GA1UdIwQYMBaAFOuXWa3ax+1lokcIZ39dvOp5\ntyzUMAwGA1UdEwQFMAMBAf8wDQYJKoZIhvcNAQEFBQADggEBAD8F+JIJ8wm9Tb6d\nLQb4BJqG+Qp7SsmCrBmxj36E9NF5ydZFdpFzhBk+FPp0qmb7QD6zVkH5KT/opO7O\nioaJ72mJWYW8YIUIo3gKg/CRIzbOh6p0rUJIrUwntE1a/LunQ5Ig+WLQrzrJjziA\neYXkm5r/B8XE6TQ9UGWFpRcV7FBFhhN2IYBiV8yAdx40b+6jMi4H7BSflfoTWdDe\n2UjFu0kEsmzzdVBAeFErYelhEhuiZEf8OhGtfnBPq4F59zRClCb94J2+yfA1ssEx\n1fs90BmQt9y07D14+MW78P3nWAQqWs5uP15V6P1xT5MHQKJIH4LhC3yTWng3rLRy\nw6/a4eE=\n-----END CERTIFICATE-----",
            "id": 7,
            "orchestra_url": "https://127.0.0.1:5000/api/queues",
            "name": "Auth1"
        },
        {
            "session_id": "vota4",
            "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAKTjrEAw+lxWMA0GCSqGSIb3DQEBBQUAMEUxCzAJBgNV\nBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX\naWRnaXRzIFB0eSBMdGQwHhcNMTMwNzIyMTYwODM0WhcNMTYwNTExMTYwODM0WjBF\nMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50\nZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\nCgKCAQEAvVH2LmO7309mX32l7tPgPWF4w2QitKnWwryJGAYoMz9HluGjoVDvK+mT\noHJFD1sdYBvG2bFPZHcj5+5V+OvVMUHb3OB0M+1tA+GBtjtLdyd3tjqYz15iBKEt\n3MTaJ+Eg2S/4CurUB7MRII+/i6MtzzuY+r5+dp9c9kruw0ztKDGONatkCWlsAON7\nacT3G1IJ6hDCsHjpi3KVub9bemLMLWLazzvhQiALs80rnlvKPAMJO5YaIZneGbS5\nLEiskygTx4THftWSis1nNrwdoWJKrj35fINIqRSMyhV8/2YbdKfjSC4SYrudT3Fw\nyEwnkuhu/yElr86/JnSN2zZlj+MjrwIDAQABo1AwTjAdBgNVHQ4EFgQUGUgho+tE\nwNXv9y0mMmufzZyu2XUwHwYDVR0jBBgwFoAUGUgho+tEwNXv9y0mMmufzZyu2XUw\nDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQUFAAOCAQEAMzYhnT8Ii10UL1hE0meD\nr+l99bymvi5284TUy8yne3FFOl4By6prpXeBSI1hOc9T2ZNJcJE/mSwMa7WQDkBC\nMPlsU1o2Xr2ewl8es1ik0/oLLU2pzsnfxmQe5j97ALgscfvkn0QO6KDeKmdd1P5c\nsLcwgiRul1drdVpjf3yMYs21IUpyBgcjvp1I7MIbYgNbxE1g3V0vGMAhG2TN3lMS\nCW7G4KBUxyp/HaAUVzz5NWOkNJ+U894d1jFacPcxcxI1zdUzyijQ8mrJvX/FqXHg\nOzzWuEmfCQld1HBMLEmQgiG0Yf3AWPpko4qy3H3BIqBpXoKVRyOCHWUQIChHJibp\n1A==\n-----END CERTIFICATE-----",
            "id": 8,
            "orchestra_url": "https://127.0.0.1:5001/api/queues",
            "name": "Auth2"
        }
    ]

```

To approve it, do:

```
    $ FRESTQ_SETTINGS=settings.py python app.py --finish <shortid> '{"status": "accepted"}' 2>/dev/null
```

Or if you want to deny that request, then do:

```
    $ FRESTQ_SETTINGS=settings.py python app.py --finish <shortid> '{"status": "denied"}' 2>/dev/null
```

To see the status of a task:

```
    $ FRESTQ_SETTINGS=settings.py ./app.py --tree 86ba85d2 --with-parents 2>/dev/null
    * create_election.orchestra_director - sequential (ef0de3c1, executing)
    |- frestq.virtual_empty_task.internal.frestq - parallel (4dba0478, finished)
    |  |- generate_private_info.orchestra_performer - sequential (17c80822, finished)
    |  |  |- frestq.virtual_empty_task.internal.frestq - external (86ba85d2, finished, root)
    |  |  |- generate_private_info_verificatum.orchestra_performer - sequential (b782e6a9, finished)
    |  |- generate_private_info.orchestra_performer - simple (f9395f0a, finished)
    |- merge_protinfo.orchestra_director - sequential (3afddaba, executing)
    |  |- frestq.virtual_empty_task.internal.frestq - synchronized (5825a61b, executing)
    |  |  |- generate_public_key.orchestra_performer - sequential (37b1399a, executing)
    |  |  |- generate_public_key.orchestra_performer - simple (14eb6a4b, reserved)
    |- return_election.orchestra_director - simple (41133962, created)
```

Example request:

POST https://127.0.0.1:5000/public_api/election
{
    "session_id": "vota1",
    "is_recurring": false,
    "callback_url": "http://example.com/callback_create_election",
    "extra": [],
    "title": "New Directive Board",
    "url": "https://example.com/election/url",
    "description": "election description",
    "question_data": {
        "question": "Who Should be President?",
        "tally_type": "ONE_CHOICE",
        "answers": ["Alice", "Bob"],
        "max": 1, "min": 0
    },
    "voting_start_date": "2013-12-06T18:17:14.457000",
    "voting_end_date": "2013-12-09T18:17:14.457000",
    "authorities": [
        {
            "name": "Auth1",
            "orchestra_url": "https://127.0.0.1:5000/api/queues",
            "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIDwTCCAqmgAwIBAgIJAJjjgNzBed6aMA0GCSqGSIb3DQEBBQUAMHcxCzAJBgNV\nBAYTAkVTMQ8wDQYDVQQIDAZNYWRyaWQxDzANBgNVBAcMBk1hZHJpZDETMBEGA1UE\nCgwKVGVzdCBBZ29yYTEPMA0GA1UEAwwGRlJFU1RRMSAwHgYJKoZIhvcNAQkBFhFl\nZHVsaXhAd2Fkb2JvLmNvbTAeFw0xMzA3MjIxNjA2NTdaFw0xNjA1MTExNjA2NTda\nMHcxCzAJBgNVBAYTAkVTMQ8wDQYDVQQIDAZNYWRyaWQxDzANBgNVBAcMBk1hZHJp\nZDETMBEGA1UECgwKVGVzdCBBZ29yYTEPMA0GA1UEAwwGRlJFU1RRMSAwHgYJKoZI\nhvcNAQkBFhFlZHVsaXhAd2Fkb2JvLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEP\nADCCAQoCggEBAMLzkBGTwH7FiA36SyjlmlV8kh+jZ//LP4PqJNJjc5SAJHGxbexI\nI2lzEFQbHMXBbHPM1NnLJitv0y8Gg9QWWBajqQeymu8O0Np7u1LG9JqNzRKIEDXk\n0SZgSoCld/cCTvtUgcT68CBE55af5EifjCI4fRf2229AiP7iibVsQ5dL/zyxLnEe\nGvuSrd+s8xyVp3pyhfHAlRe+ftATjJ3wBUGCmUr9d1lS9fQziCIYzeq9fWnwxCz/\ngp76930iUEIp7vYQzSfgbWSuQgrlrZUOIR/2+Rfk2Y1S6dE9NwjGtLp3kMOIeM9A\nclA/YyPUR47DX2yHxjIUz7jLT+li5Wrx7JUCAwEAAaNQME4wHQYDVR0OBBYEFOuX\nWa3ax+1lokcIZ39dvOp5tyzUMB8GA1UdIwQYMBaAFOuXWa3ax+1lokcIZ39dvOp5\ntyzUMAwGA1UdEwQFMAMBAf8wDQYJKoZIhvcNAQEFBQADggEBAD8F+JIJ8wm9Tb6d\nLQb4BJqG+Qp7SsmCrBmxj36E9NF5ydZFdpFzhBk+FPp0qmb7QD6zVkH5KT/opO7O\nioaJ72mJWYW8YIUIo3gKg/CRIzbOh6p0rUJIrUwntE1a/LunQ5Ig+WLQrzrJjziA\neYXkm5r/B8XE6TQ9UGWFpRcV7FBFhhN2IYBiV8yAdx40b+6jMi4H7BSflfoTWdDe\n2UjFu0kEsmzzdVBAeFErYelhEhuiZEf8OhGtfnBPq4F59zRClCb94J2+yfA1ssEx\n1fs90BmQt9y07D14+MW78P3nWAQqWs5uP15V6P1xT5MHQKJIH4LhC3yTWng3rLRy\nw6/a4eE=\n-----END CERTIFICATE-----"
        },
        {
            "name": "Auth2",
            "orchestra_url": "https://127.0.0.1:5001/api/queues",
            "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAKTjrEAw+lxWMA0GCSqGSIb3DQEBBQUAMEUxCzAJBgNV\nBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX\naWRnaXRzIFB0eSBMdGQwHhcNMTMwNzIyMTYwODM0WhcNMTYwNTExMTYwODM0WjBF\nMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50\nZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\nCgKCAQEAvVH2LmO7309mX32l7tPgPWF4w2QitKnWwryJGAYoMz9HluGjoVDvK+mT\noHJFD1sdYBvG2bFPZHcj5+5V+OvVMUHb3OB0M+1tA+GBtjtLdyd3tjqYz15iBKEt\n3MTaJ+Eg2S/4CurUB7MRII+/i6MtzzuY+r5+dp9c9kruw0ztKDGONatkCWlsAON7\nacT3G1IJ6hDCsHjpi3KVub9bemLMLWLazzvhQiALs80rnlvKPAMJO5YaIZneGbS5\nLEiskygTx4THftWSis1nNrwdoWJKrj35fINIqRSMyhV8/2YbdKfjSC4SYrudT3Fw\nyEwnkuhu/yElr86/JnSN2zZlj+MjrwIDAQABo1AwTjAdBgNVHQ4EFgQUGUgho+tE\nwNXv9y0mMmufzZyu2XUwHwYDVR0jBBgwFoAUGUgho+tEwNXv9y0mMmufzZyu2XUw\nDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQUFAAOCAQEAMzYhnT8Ii10UL1hE0meD\nr+l99bymvi5284TUy8yne3FFOl4By6prpXeBSI1hOc9T2ZNJcJE/mSwMa7WQDkBC\nMPlsU1o2Xr2ewl8es1ik0/oLLU2pzsnfxmQe5j97ALgscfvkn0QO6KDeKmdd1P5c\nsLcwgiRul1drdVpjf3yMYs21IUpyBgcjvp1I7MIbYgNbxE1g3V0vGMAhG2TN3lMS\nCW7G4KBUxyp/HaAUVzz5NWOkNJ+U894d1jFacPcxcxI1zdUzyijQ8mrJvX/FqXHg\nOzzWuEmfCQld1HBMLEmQgiG0Yf3AWPpko4qy3H3BIqBpXoKVRyOCHWUQIChHJibp\n1A==\n-----END CERTIFICATE-----"
        }
    ]
}