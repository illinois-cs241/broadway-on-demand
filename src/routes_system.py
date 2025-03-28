from flask import request
from http import HTTPStatus
from src import db
from config import SYSTEM_API_TOKEN


class SystemRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/system/feedback/", methods=["POST"])
        def system_feedback():
            if request.headers.get("Authorization") != ("Bearer %s" % SYSTEM_API_TOKEN):
                return "Unauthorized", HTTPStatus.UNAUTHORIZED
            data = request.json()
            if "run_id" not in data or "feedback" not in data:
                return "Missing 'run_id' or 'feedback' fields.", HTTPStatus.BAD_REQUEST

        @blueprint.route("/system/<cid>/<runid>/<netid>/statusping", methods=["POST"])
        def set_job_status(cid, runid, netid):
            if request.headers.get("Authorization") != ("Bearer %s" % SYSTEM_API_TOKEN):
                return "Unauthorized", HTTPStatus.UNAUTHORIZED
            data = request.json
            if not data or not data["status"]:
                return "New status not given.", HTTPStatus.BAD_REQUEST
            build_url = None
            try:
                build_url = data["build_url"]
            except Exception:
                pass
            try:
                db.set_jenkins_run_status(cid, runid, data["status"], build_url, netid)
            except Exception as e:
                print(e, flush=True)
                return "Could not save status.", HTTPStatus.INTERNAL_SERVER_ERROR
            return "Status saved.", HTTPStatus.OK
