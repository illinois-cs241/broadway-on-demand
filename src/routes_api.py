import json
import logging
from flask import request, abort
from http import HTTPStatus

from src import db, util, auth, bw_api
from src.common import verify_student_or_staff
from src.sched_api import ScheduledRunStatus

class ApiRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/jenkins/run_status/<cid>/<runId>", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        @util.catch_request_errors
        def student_get_job_status(netid, cid, runId):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)
            return util.success(db.get_jenkins_run_status_single(cid, runId, netid)['status'], 200)
          
        @blueprint.route("/api/<cid>/<aid>/trigger_scheduled_run/<scheduled_run_id>", methods=["POST"])
        @auth.require_system_auth
        def trigger_scheduled_run(cid, aid, scheduled_run_id):
            sched_run = db.get_scheduled_run_by_scheduler_id(cid, aid, scheduled_run_id)
            if sched_run is None:
                logging.warning("Received trigger scheduled run request for scheduled_run_id '%s' but cannot find corresponding run.", scheduled_run_id)
                return util.error("")
            if sched_run["status"] != ScheduledRunStatus.SCHEDULED:
                logging.warning("Received trigger scheduled run for _id '%s' but this run has status '%s', which is not 'scheduled'.", str(sched_run["_id"]), sched_run["status"])
                return util.error("")

            # If roster is not provided, use course roster
            if sched_run["roster"] is None:
                course = db.get_course(cid)
                if course is None:
                    return util.error("")
                netids = course["student_ids"]
            # If a roster is provided, use it
            else:
                netids = sched_run["roster"]
            
            # Start broadway grading run
            bw_run_id = bw_api.start_grading_run(cid, f"{aid}_{sched_run['_id']}", netids, sched_run["due_time"])
            if bw_run_id is None:
                logging.warning("Failed to trigger run with broadway")
                db.update_scheduled_run_status(sched_run["_id"], ScheduledRunStatus.FAILED)
                return util.error("")
            else:
                db.update_scheduled_run_status(sched_run["_id"], ScheduledRunStatus.RAN)
                db.update_scheduled_run_bw_run_id(sched_run["_id"], bw_run_id)
            return util.success("")

