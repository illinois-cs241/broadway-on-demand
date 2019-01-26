import os
import json

from slackclient import SlackClient
from slackeventsapi import SlackEventAdapter

from flask import Flask
from flask import request
from flask import jsonify

from src import util, common, bw_api

class SlackBot:
    def __init__(self, app):
        cmd_dict = {}

        slack_token = os.environ["SLACK_API_TOKEN"]
        slack_secret = os.environ["SLACK_SIGNING_SECRET"]

        slack_client = SlackClient(slack_token)
        slack_events_adapter = SlackEventAdapter(slack_secret)

        def get_user_email(user_id):
            res = slack_client.api_call("users.info", user=user_id)

            if not res["ok"]:
                raise Exception("failed to get uset email: " + res["error"])

            return res["user"]["profile"]["email"]

        def command(name):
            def proc(f):
                cmd_dict[name] = f

            return proc

        def in_channel(user, msg):
            return jsonify({
                "response_type": "in_channel",
                "text": "<@" + user + "> " + msg
            })

        def error(user, msg):
            return jsonify({
                "response_type": "ephemeral",
                "text": "<@" + user + "> " + msg
            })

        # add extra commands here
        @command("grade")
        def cmd_grade(user, netid, args):
            """
            argument: <course> <assignment> <netid-1> [netid_2] ...
            """

            if len(args) < 3:
                return error(user, "usage: grade <course> <assignment> <netid-1> [netid_2] ...")

            cid = args[0]
            aid = args[1]
            netids = args[2:]

            # check netid is admin
            if not common.verify_admin(cid, netid):
                return error(user, "you don't have the privilege to do that")

            # check netids are students
            for student in netids:
                if not common.verify_student(cid, student):
                    return error(user, "netid `{}` is not a student of the course `{}`".format(student, cid))

            # request grading run
            run_id = bw_api.start_grading_run(cid, aid, netids, now_timestamp())

            if run_id is None:
                return in_channel(user, "failed to request grading run")

            return in_channel(user, "grading run requested, run_id `{}`".format(run_id))
            # return in_channel(user, "grading {} for {}:{}".format(", ".join(netids), course, assignment))

        @app.route("/slack/cmd", methods=["POST"])
        def slack_cmd():
            cmd = request.form.get("command")
            args = request.form.get("text").split()
            user = request.form.get("user_id")

            ts = request.headers.get("X-Slack-Request-Timestamp")
            sig = request.headers.get("X-Slack-Signature")
            print("{}, {}".format(ts, sig))
            # request.data = request.get_data()
            result = slack_events_adapter.server.verify_signature(ts, sig)

            email = get_user_email(user)
            netid = email.split("@")[0]            

            if not len(args):
                return error(user, "wrong argument")
            else:
                cmd = args[0]
                if cmd in cmd_dict:
                    return cmd_dict[cmd](user, netid, args[1:])
                else:
                    return error(user, "command `{}` does not exist".format(cmd))

if __name__ == "__main__":
    app = Flask(__name__)
    SlackBot(app)
    app.run(host="0.0.0.0", port=3133)
