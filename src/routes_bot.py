import os
import json
import re

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

RUN_ID_PATTERN = r"[0-9a-f]{24}"

class SlackRequest:
    def __init__(self, bot, user, form):
        self.user = user
        self.email = bot.get_user_email(self.user)
        self.netid = self.email.split("@")[0]

        self.response_url = form.get("response_url")

    def public(self, msg, *attach_l, attach=[]):
        """
        Visible to everyone in the channel
        """

        return {
            "response_type": "in_channel",
            "text":
                "<@" + self.user + "> " + msg if msg is not None else None,
            "attachments": list(attach_l) + attach
        }

    def private(self, msg, *attach_l, attach=[]):
        """
        Only visible to the command sender
        """

        return {
            "response_type": "ephemeral",
            "text": msg if msg is not None else None,
            "attachments": list(attach_l) + attach
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

class Command(SlackRequest):
    """Wrapper class for a command"""

    def __init__(self, bot, form):
        self.cmd = form.get("command")
        self.args = form.get("text").split()

        SlackRequest.__init__(self, bot, form.get("user_id"), form)

class Action(SlackRequest):
    """wrapper class for an action"""

    def __init__(self, bot, form):
        self.callback_id = form.get("callback_id")
        self.message = form.get("message")

        SlackRequest.__init__(self, bot, form["user"]["id"], form)

    def private(self, *args, **kargs):
        obj = super().private(*args, **kargs)
        res = requests.post(self.response_url, data=json.dumps(obj))

        if res.status_code != 200:
            raise Exception("Callback failed: " + res.text)

    def public(self, *args, **kargs):
        obj = super().public(*args, **kargs)
        res = requests.post(self.response_url, data=json.dumps(obj))

        if res.status_code != 200:
            raise Exception("Callback failed: " + res.text)

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

class AI:
    """just passed the Turing test"""

    colors = [ "#1abc9c", "#2ecc71", "#3498db", "#9b59b6", "#f1c40f", "#e67e22", "#e74c3c" ]

    positive_prompts = [ "Here you go" ]
    negative_prompts = [ "Uh-oh" ]

    @staticmethod
    def color():
        return choice(AI.colors)

    @staticmethod
    def positive():
        return choice(AI.positive_prompts)

    @staticmethod
    def negative():
        return choice(AI.negative_prompts)

class Attachment:
    @staticmethod
    def random_color(msg):
        return {
            "color": AI.color(),
            "text": msg,
            "mrkdwn_in": ["text"]
        }

class SlackBot(SlackClient):
    """
    Basic slack bot class
    Handles incoming commands and dispatch of command handlers
    """

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
                    return cmd.private("Wrong argument", attach=[
                        Attachment.random_color("{}\nUsage: `{} {}`".format(help_msg, cmd.cmd, f.__doc__))
                    ]) # return usage

            self.cmd_dict[name] = (wrapper, help_msg)

            return f # preseve docstring

        return decorator

    def action(self, name):
        def decorator(f):
            self.action_dict[name] = f
            return f # preseve docstring

        return decorator

    def print_help(self, cmd):
        ret = [] # prepend an empty line

        for _, (f, msg) in self.cmd_dict.items():
            ret.append("{}\n`{} {}`".format(msg, cmd.cmd, f.__doc__))

        return cmd.public("Some help?", attach=[
            Attachment.random_color(cont) for cont in ret
        ])

    def __init__(self, app):
        self.cmd_dict = {}
        self.action_dict = {}

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

        @app.route("/slack/action", methods=["POST"])
        @signer.check_sig
        def slack_action():
            """Parse and dispatch action handlers"""

            action = Action(self, json.loads(request.form.get("payload")))

            if action.callback_id in self.action_dict:
                self.action_dict[action.callback_id](self, action)
                return ""
            else:
                action.private("Action `{}` does not exist".format(action.callback_id))
                return ""

class BroadwayBot(SlackBot):
    """
    Class that implements all broadway related commands
    """

    def __init__(self, app):
        super().__init__(app)

        @self.action("run_status")
        def action_run_status(bot, action):
            text = action.message.get("text")
            attachments = action.message.get("attachments", [])

            text += "\n".join([ attach.get("text", "") for attach in attachments ])
            
            result = re.search(RUN_ID_PATTERN, text)

            if result is None:
                action.private("This message contains no run id")
                return

            run_id = result.group(0)

            run = db.get_grading_run(run_id)

            if run is None:
                action.private("Grading run `{}` does not exist".format(run_id))
                return

            status = bw_api.get_grading_run_status(run["course_id"], run["assignment_id"], run_id)

            if status is None:
                action.private(None, Attachment.random_color("Failed to get status for run `{}`". format(run_id)))
                return

            action.private(None, Attachment.random_color("Run `{}`: {}".format(run_id, status)))
            return

        @self.command("list", "List courses/assignments")
        def cmd_list(bot, cmd, *courses):
            """list [course-1] [course-2] ..."""
            
            if len(courses):
                # list assignments in courses

                prompt_list = []

                for course in courses:
                    if not common.verify_course(course):
                        return cmd.public(AI.negative(), attach=[
                            Attachment.random_color("Course `{}` does not exist".format(course))
                        ])

                    assigns = db.get_assignments_for_course(course)

                    if assigns is not None:
                        if len(assigns):
                            ids = [ "`" + assign["assignment_id"] + "`" for assign in assigns ]

                            prompt_list.append(Attachment.random_color(
                                "Course `{}` has the following assignment(s)\n{}" \
                                .format(course, ", ".join(ids))
                            ))
                        else:
                            prompt_list.append(Attachment.random_color(
                                "Course `{}` has no assignment"
                            ))
                    else:
                        prompt_list.append(Attachment.random_color(
                            "Course `{}` does not exist"
                        ))

                return cmd.public(AI.positive(), attach=prompt_list)

            else:
                # assuming admin_ids is a subset of staff_ids
                courses = db.get_all_courses()
                course_names = [ course["_id"] for course in courses ]

                if len(courses):
                    return cmd.public(AI.positive(), attach=[
                        Attachment.random_color(
                            "You have access to the following course(s)\n{}" \
                            .format(", ".join([ "`" + name + "`" for name in course_names ]))
                        )
                    ])
                else:
                    return cmd.public(AI.negative(), attach=[
                        Attachment.random_color("There is no course")
                    ])

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
                    return cmd.public(None, Attachment.random_color("Failed to get status for run `{}`". format(run_id)))

                return cmd.public(None, Attachment.random_color("Run `{}`: {}".format(run_id, status)))

            return cmd.public("Just a sec")

        # add extra commands here
        @self.command("grade", "Request grading run")
        def cmd_grade(bot, cmd, cid, aid, *netids):
            """grade <course> <assignment> <netid-1> [netid-2] ..."""

            # check course exists
            if not common.verify_course(cid):
                return cmd.public("Course `{}` does not exist".format(cid))

            # check assignment exists
            if not common.verify_assignment(cid, aid):
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
                    return cmd.public(None, Attachment.random_color("Failed to request grading run"))
                else:
                    # run created
                    for student in netids:
                        db.add_grading_run(cid, aid, student, ts, run_id)

                    return cmd.public(None, Attachment.random_color("Grading run requested, run_id `{}`".format(run_id)))

            return cmd.public("Requesting")

        @self.command("help", "Print help message")
        def cmd_help(bot, cmd):
            """help"""
            return bot.print_help(cmd)
