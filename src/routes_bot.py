import os
import json

from slackclient import SlackClient
from slackeventsapi import SlackEventAdapter

from flask import Flask
from flask import request
from flask import jsonify
from flask import abort

from src import db, util, common, bw_api
from src import config

import requests
import threading

class SlackBot:
    def __init__(self, app):
        cmd_dict = {}

        slack_client = SlackClient(config.SLACK_API_TOKEN)
        slack_events_adapter = SlackEventAdapter(config.SLACK_SIGNING_SECRET)

        def get_user_email(user_id):
            res = slack_client.api_call("users.info", user=user_id)

            if not res["ok"]:
                raise Exception("failed to get uset email: " + res["error"])

            return res["user"]["profile"]["email"]

        def command(name):
            def proc(f):
                cmd_dict[name] = f

            return proc

        def public(user, msg):
            return jsonify({
                "response_type": "in_channel",
                "text": "<@" + user + "> " + msg
            })

        def private(user, msg):
            return jsonify({
                "response_type": "ephemeral",
                "text": "<@" + user + "> " + msg
            })

        def delayed(user, msg):
            response_url = request.form.get("response_url")
            
            obj = {
                "response_type": "in_channel",
                "text": "<@" + user + "> " + msg
            }

            requests.post(response_url, data=obj)

        def delayed(user):
            response_url = request.form.get("response_url")

            def proc(f):
                def wrapper():
                    res = f()

                    obj = {
                        "response_type": "in_channel",
                        "text": "<@" + user + "> " + res
                    }

                    # print("responding to "+ response_url)

                    res = requests.post(response_url, data=json.dumps(obj))

                    if res.status_code != 200:
                        raise Exception("callback failed: " + res.text)

                thread = threading.Thread(target=wrapper, args=())
                thread.daemon = True
                thread.start()

            return proc

        @command("status")
        def cmd_status(user, netid, args):
            """usage: status <run-id>"""

            if not len(args):
                return private(user, "usage: status <run-id>")

            run_id = args[0]
            run = db.get_grading_run(run_id)

            if run is None:
                return public(user, "grading run `{}` does not exist".format(run_id))

            @delayed(uesr)
            def cont():
                status = bw_api.get_grading_run_status(run["cid"], run["aid"], run_id)

                if status is None:
                    return "failed to get status for run `{}`". format(run_id)

                return "run `{}`: {}".format(run_id, status)

            return public("fetching")

        # add extra commands here
        @command("grade")
        def cmd_grade(user, netid, args):
            """usage: <course> <assignment> <netid-1> [netid-2] ..."""

            if len(args) < 3:
                return private(user, )

            cid = args[0]
            aid = args[1]
            netids = args[2:]

            # check course exists
            if not common.verify_cid(cid):
                return private(user, "course `{}` does not exist".format(cid))

            # check assignment exists
            if not common.verify_aid(cid, aid):
                return private(user, "assignment `{}` does not exist in courses `{}`".format(aid, cid))

            # check netid is admin
            if not common.verify_admin(netid, cid):
                return private(user, "you don't have the privilege to do that")

            # check netids are students
            for student in netids:
                if not common.verify_student(student, cid):
                    return private(user, "netid `{}` is not a student of the course `{}`".format(student, cid))

            @delayed(user)
            def cont():
                # request grading run
                ts = util.now_timestamp()

                try:
                    run_id = bw_api.start_grading_run(cid, aid, netids, ts)
                except:
                    run_id = None

                if run_id is None:
                    return "failed to request grading run"
                else:
                    # run created
                    for student in netids:
                        db.add_grading_run(cid, aid, student, ts, run_id)

                    return "grading run requested, run_id `{}`".format(run_id)

            return public(user, "processing")

        @app.route("/slack/cmd", methods=["POST"])
        def slack_cmd():
            ts = request.headers.get("X-Slack-Request-Timestamp")
            sig = request.headers.get("X-Slack-Signature")
            signed = slack_events_adapter.server.verify_signature(ts, sig)

            if not signed:
                return abort(403)

            cmd = request.form.get("command")
            args = request.form.get("text").split()
            user = request.form.get("user_id")

            email = get_user_email(user)
            netid = email.split("@")[0]            

            if not len(args):
                return private(user, "wrong argument")
            else:
                cmd = args[0]
                if cmd in cmd_dict:
                    return cmd_dict[cmd](user, netid, args[1:])
                else:
                    return private(user, "command `{}` does not exist".format(cmd))

if __name__ == "__main__":
    app = Flask(__name__)
    SlackBot(app)
    app.run(host="0.0.0.0", port=3133)
