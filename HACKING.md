Election Orchestra
==================

This software orchestrates the authorities servers to create election
public-keys and perform the tallying using verificatum.

Public API (Director)
---------------------

The public API will include a publicly available directory over https listing
for each election in the following form:

 elections/
 |- 554ef33a44/
    |- protInfo.xml
    |- protInfo.sha2
    |- tallies/
       |- 586ea3b591/
          |- ciphertexts
          |- cleartexts
          |- tally_586ea3b591.tar.bz2
          |- tally_586ea3b591.sha2

This listing can be shared directly via http with your favourite http server,
over with SSL for security.

POST /election
==============

Description:
    Creates an election, with the given input data. This involves communicating
    with the different election authorities to generate the joint public key.

Input:
    - session_id
    - title
    - is_recurring
    - callback_url
    - caller_ssl_cert
    - extra
    - authorities
        - name
        - orchestra_url
        - ssl_cert

Output:
    expiration_date

Callback url:
    Callback url will be called to update the caller with status. The calls
    will be in json with two main keys: status and data.

    {
        "status": "finished",
        "reference": {
            "session_id": <id>,
            "action": "POST /election"
        },
        "data": {
            "protinfo_url": <url>,
            "protinfo_hash": ""
        }
    }

    {
        "status": "error",
        "reference": {
            "session_id": <id>,
            "action": "POST /election"
        },
        "data": {
            "message": "<error message>"
        }
    }

POST /tally
===========

Tallies an election, involves communicating with the election authorities
that have to cooperate to do the tally.

Input:
    - session_id
    - votes_url
    - votes_hash
    - callback_url
    - extra

Output:
    - tally_id
    - expiration_date

Callback url:
    Callback url will be called to update the caller with status. The calls
    will be in json with two main keys: status and data.

    {
        "status": "finished",
        "reference": {
            "tally_id": <id>,
            "action": "POST /tally"
        },
        "data": {
            "tally_url": <url>,
            "tally_hash": ""
        }
    }

    {
        "status": "error",
        "reference": {
            "tally_id": <id>,
            "action": "POST /tally"
        },
        "data": {
            "message": "<error message>"
        }
    }

Internal API
------------

Tally process from the REST task queue point of view
====================================================

From A to B_n:

This call is used to collect approval by the admins for the tallying. This
happens when the director of the election orchestra receives a POST /tally call.

POST /task
{
    "action": "election-orchestra.approve_tally",
    "input_data": {
        "session_id": "2",
        "tally_id": "1",
        "tally_url": "https://example.com/broker/data/3ef338061/",
        "tally_hash": "",
    },
    "expiration_date": "date",
    "broker_url": "https://example.com/broker/",
}
answer:
STATUS 201
{
    "status": "waiting",
    "task_id": "98105eabc",
    // this is when broker should ask again about the status if it didn't
    // receive any more news from us
    "pingback_date": "date",
    "info": "waiting on authority operator to review",
    "data": {
    }
}

From B_n to A:
PUT /task/98105eabc/status
{
    "status": "finished",
    "task_id": "98105eabc",
    "data": {
        "result": "APPROVED"
    }
}

From B_n to A:
{
    "status": "finished",
    "task_id": "98105eabc",
    "data": {
        "result": "DENIED"
    }
}

When pingback_date expires, A calls to B_n to GET /task/98105eabc/status,
receiving similar type of answers.

If A receives a denied request, tallying process is cancelled, and this is
notified to the election-orchestra client.

However if everything is fine, then we have the approval of all authorities, and
thus the real tally process can begin to be requested in another set of tasks.
These tasks however need to do multiparty synchronization. To do that, we will
use in a first version a naive algorithm.

From A to B_n:

POST /task
{
    "action": "election-orchestra.perform_tally",
    "input_data": {
        "tally_id": "1", // all other data was already sent previously
    },
    "expiration_date": "date",
    "broker_url": "https://example.com/broker/",
}
answer:
STATUS 201
{
    "status": "waiting",
    "task_id": "11105ea5d",
    "pingback_date": "date",
    // control message are "internal" of the task protocol
    "is_control": true,
    "info": "busy working on other things",
    "data": {
    }
}
other possible answers, that can also be received via a ping back update:
STATUS 201
{
    "status": "ready",
    "task_id": "11105ea5d",
    // ready means that B_n is ready to start processing, but is waiting for
    // the other authorities to also be ready. If timeout_date is reached
    // and this task is still in ready state, it will expire
    "expiration_date": "date",
    "pingback_date": "date",
    // control message are "internal" of the task protocol
    "is_control": true,
    "data": {
    }
}
STATUS 201
{
    "status": "working",
    "task_id": "11105ea5d",
    // working means that B_n is busy doing stuff (processing votes/tallying)
    // together with the other nodes. Expiration date means that past that date,
    // the task will be killed because it was taking too much time (this is to
    // avoid tasks that get all resources or get stuck)
    "expiration_date": "date",
    "pingback_date": "date",
    // control message are "internal" of the task protocol
    "is_control": true,
    "data": {
    }
}
STATUS 403 // denied
{
    "status": "error",
    "task_id": "11105ea5d",
    "info": "denied because the tallying was not approved by operator" // example
    "data": {
    }
}

STATUS 200
{
    "status": "finished",
    "task_id": "11105ea5d",
    "data": {
        "results_url": "https://example.com/frestq/11105ea5d/data"
    }
}

// when a task expires because for example it was ready and other authorities
// were not ready before expiration_time, broker needs to request a new task
// to B_n
STATUS 400 // expired
{
    "status": "expired",
    "task_id": "11105ea5d",
    "is_control": true,
    "data": {
    }
}


@frestq.task(action="election-orchestra-post_tally", queue=director_queue)
@frestq.permissions(check_election_certificate)
def post_tally(request):
    '''
    Example of a task performed by the election-orchestra director
    '''

    election = get_object(Election, session_id=request.data.session_id)
    tally = Tally(election)
    tally.votes = download(ciphertexts_url, ciphertexts_hash)
    tally.save()

    approve_tally = ChordTask()
    for auth in authorities:
        task = Task(worker=auth.url,
            action="election-orchestra.approve_tally",
            receiver_ssl_cert=auth.ssl_cert,
            data=dict(
                tally_id=tally.id,
                session_id=tally.election.session_id)
            ),
            async_data=dict(
                votes__path=tally.votes_path
            )
        approve_tally.append(task)
    request.current_task.add(approve_tally)

    perform_tally = SynchronousTasks(algorithm="naive")
    for auth in authorities:
        tally_task = Task(worker=auth.url,
            action="election-orchestra.perform_tally",
            receiver_ssl_cert=auth.ssl_cert,
            data=dict(tally_id=tally.id))
        perform_tally.append(task)

    request.current_task.expiration_time = now() + delta(hours=24)
    request.current_task.add(approve_tally)


def check_director_certificate(request):
    '''
    Example of permissions decorator
    '''
    election = get_object(Election, session_id=request.data.session_id)
    if not election.director_ssl_cert.check(request.ssl_cert):
        raise frestq.UnauthorizedError(info="invalid ssl director certificate")

@frestq.task(action="election-orchestra.approve_tally", queue=orchestra_queue)
@frestq.permissions(check_director_certificate)
def approve_tally(request):
    '''
    Example of a task performed by an election-orchestra authority requested by
    a director
    '''

    # NOTE that the usual interface that the authorities operator will use will
    # NOT be a frestq interface, but a taylor-made interface for elections and
    # tallies. It'll be specific for this and user-friendly.

    # There will also be an interface for frestq, but that will be completely
    # differet.
    tally = Tally(election__session_id=request.data.session_id,
        id=request.data.tally_id)
    # stores votes in a persistent file
    tally.set_votes(request.async_data.votes__path)
    tally.status = "PENDING"
    tally.task_id = request.current_task.id
    tally.save()

    request.current_task.status="waiting"
    request.current_task.info = "waiting on authority operator to review",


// app.py:
    orchestra_queue = frestq.Queue("orchestra")
    director_queue = frestq.Queue("director")

    app.register_queue(orchestra_queue)
    app.register_queue(director_queue)



class Message
    id = ""
    received_date = ""
    action = ""
    input_data = "{}"
    input_method = "POST"
    task_id = 13
    input_path = "/task/blah"
    callback_broker
    input_ssl_cert = ""
    output_status = "200"
    output_data = ""
    expiration_time = ""
    expires = true
    pingback_date = ""
    needs_pingback = true
    info = ""