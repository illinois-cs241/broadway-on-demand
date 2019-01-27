import os
import json

from random import choice
from functools import wraps

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

class Command:
    """Wrapper class for a command"""

    def __init__(self, bot, form):
        self.cmd = form.get("command")
        self.args = form.get("text").split()
        self.user = form.get("user_id")

        self.email = bot.get_user_email(self.user)
        self.netid = self.email.split("@")[0]
        self.response_url = request.form.get("response_url")

    def public(self, msg, attach=[]):
        """
        Visible to everyone in the channel
        """

        return {
            "response_type": "in_channel",
            "text": "<@" + self.user + "> " + msg,
            "attachments": attach
        }

    def private(self, msg, attach=[]):
        """
        Only visible to the command sender
        """

        return {
            "response_type": "ephemeral",
            "text": "<@" + self.user + "> " + msg,
            "attachments": attach
        }

    def delayed(self, f):
        """
        Delayed command handler
        Used for response after 3000ms
        """

        def wrapper():
            res = requests.post(self.response_url, data=json.dumps(f()))

            if res.status_code != 200:
                raise Exception("Callback failed: " + res.text)

        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()

        return

class SlackSigner:
    """
    Check signatures of slack requests
    """

    def __init__(self, secret):
        self.adapter = SlackEventAdapter(secret)

    # decorator
    def check_sig(self, f):
        @wraps(f)
        def wrapper():
            ts = request.headers.get("X-Slack-Request-Timestamp")
            sig = request.headers.get("X-Slack-Signature")
            signed = self.adapter.server.verify_signature(ts, sig)

            if not signed:
                return abort(403)
            else:
                return f()

        return wrapper

class SlackBot(SlackClient):
    """
    Basic slack bot class
    Handles incoming commands and dispatch of command handlers
    """

    colors = [ "#1abc9c", "#2ecc71", "#3498db", "#9b59b6", "#f1c40f", "#e67e22", "#e74c3c" ]

    def get_user_email(self, user_id):
        res = self.api_call("users.info", user=user_id)

        if not res["ok"]:
            raise Exception("Failed to get uset email: " + res["error"])

        return res["user"]["profile"]["email"]

    def command(self, name, help_msg):
        def decorator(f):
            @wraps(f)
            def wrapper(cmd):
                try:
                    # try match function parameters
                    return f(self, cmd, *cmd.args[1:])
                except TypeError:
                    return cmd.private("Wrong argument", attach = [
                        {
                            "color": choice(SlackBot.colors),
                            "text": "{}\nUsage: `{} {}`".format(help_msg, cmd.cmd, f.__doc__)
                        }
                    ]) # return usage

            self.cmd_dict[name] = (wrapper, help_msg)

            return f # preseve docstring

        return decorator

    def print_help(self, cmd):
        ret = [] # prepend an empty line

        for _, (f, msg) in self.cmd_dict.items():
            ret.append("{}\n`{} {}`".format(msg, cmd.cmd, f.__doc__))

        return cmd.public("Some help?", attach=[
            {
                "color": choice(SlackBot.colors),
                "text": cont
            } for cont in ret
        ])

    def __init__(self, app):
        self.cmd_dict = {}

        SlackClient.__init__(self, config.SLACK_API_TOKEN)

        signer = SlackSigner(config.SLACK_SIGNING_SECRET)

        @app.route("/slack/cmd", methods=["POST"])
        @signer.check_sig
        def slack_cmd():
            """Parse and dispatch command handlers"""

            cmd = Command(self, request.form)

            if not len(cmd.args):
                return jsonify(self.print_help(cmd))
            else:
                if cmd.args[0] in self.cmd_dict:
                    return jsonify(self.cmd_dict[cmd.args[0]][0](cmd))
                else:
                    return jsonify(cmd.private("Command `{}` does not exist".format(cmd.args[0])))

class BroadwayBot(SlackBot):
    """
    Class that implements all broadway related commands
    """

    def __init__(self, app):
        super().__init__(app)

        @self.command("status", "Check status of a grading run")
        def cmd_status(bot, cmd, run_id):
            """status <run-id>"""

            run = db.get_grading_run(run_id)

            if run is None:
                return cmd.public("Grading run `{}` does not exist".format(run_id))

            @cmd.delayed
            def cont():
                status = bw_api.get_grading_run_status(run["course_id"], run["assignment_id"], run_id)

                if status is None:
                    return cmd.public("Failed to get status for run `{}`". format(run_id))

                return cmd.public("Run `{}`: {}".format(run_id, status))

            return cmd.public("Fetching")

        # add extra commands here
        @self.command("grade", "Request grading run")
        def cmd_grade(bot, cmd, cid, aid, *netids):
            """grade <course> <assignment> <netid-1> [netid-2] ..."""

            # check course exists
            if not common.verify_cid(cid):
                return cmd.public("Course `{}` does not exist".format(cid))

            # check assignment exists
            if not common.verify_aid(cid, aid):
                return cmd.public("Assignment `{}` does not exist in course `{}`".format(aid, cid))

            # check netid is admin
            if not common.verify_admin(cmd.netid, cid):
                return cmd.public("You don't have the privilege to do that")

            # check netids are students
            for student in netids:
                if not common.verify_student(student, cid):
                    return cmd.public("NetID `{}` is not a student of the course `{}`".format(student, cid))

            @cmd.delayed
            def cont():
                # request grading run
                ts = util.now_timestamp()

                try:
                    run_id = bw_api.start_grading_run(cid, aid, netids, ts)
                except:
                    run_id = None

                if run_id is None:
                    return cmd.public("Failed to request grading run")
                else:
                    # run created
                    for student in netids:
                        db.add_grading_run(cid, aid, student, ts, run_id)

                    return cmd.public("Grading run requested, run_id `{}`".format(run_id))

            return cmd.public("Processing")

        @self.command("help", "Print help message")
        def cmd_help(bot, cmd):
            """help"""
            return bot.print_help(cmd)
