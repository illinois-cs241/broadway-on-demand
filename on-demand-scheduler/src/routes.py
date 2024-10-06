from flask import request, jsonify
from datetime import datetime
import uuid
from http import HTTPStatus

from src.utils import trigger_run, contains_job

class Routes:

    def __init__(self, blueprint, scheduler, token):

        @blueprint.route("/api/scheduled_runs", methods=["GET"])
        def get_scheduled_runs():
            runs_json = {}
            for j in scheduler.get_jobs():
                runs_json[j.id] = j.next_run_time

            return jsonify({"scheduled_runs": runs_json}), HTTPStatus.OK

        @blueprint.route("/api/schedule_run", methods=["POST"])
        def schedule_run():
            time = request.form.get("time")
            if time is None:
                return "Time not set", HTTPStatus.BAD_REQUEST
            course_id = request.form.get("course_id")
            if course_id is None:
                return "Course id not set", HTTPStatus.BAD_REQUEST
            assignment_id = request.form.get("assignment_id")
            if assignment_id is None:
                return "Assignment id not set", HTTPStatus.BAD_REQUEST

            run_id = uuid.uuid4().hex
            scheduler.add_job(trigger_run, trigger="date", next_run_time=time, id=run_id, args=[course_id, assignment_id, run_id, token])

            res = {"scheduled_run_id": run_id}
            return jsonify(res)

        @blueprint.route("/api/<scheduled_run_id>", methods=["POST"])
        def update_scheduled_run(scheduled_run_id):
            if not contains_job(scheduler, scheduled_run_id):
                return f"Scheduler does not contain run with id {scheduled_run_id}", HTTPStatus.BAD_REQUEST

            time = request.form.get("time")
            if time is None:
                return "Time not set", HTTPStatus.BAD_REQUEST

            scheduler.modify_job(scheduled_run_id, next_run_time=time)
            return "", HTTPStatus.OK

        @blueprint.route("/api/<scheduled_run_id>", methods=["DELETE"])
        def delete_scheduled_run(scheduled_run_id):
            if not contains_job(scheduler, scheduled_run_id):
                return f"Scheduler does not contain run with id {scheduled_run_id}", HTTPStatus.BAD_REQUEST
            scheduler.remove_job(scheduled_run_id)
            return "", HTTPStatus.OK
