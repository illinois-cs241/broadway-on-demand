import json
import logging
from flask import request, abort
from http import HTTPStatus

from src import db, jenkins_api, util, auth
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
            try:
                return util.success(
                    db.get_jenkins_run_status_single(cid, runId, None)["status"], 200
                )
            except Exception:
                return util.error("")

        @blueprint.route(
            "/api/<cid>/assignment/<aid>/trigger_scheduled_run/<scheduled_run_id>",
            methods=["POST"],
        )
        @auth.require_system_auth
        def trigger_scheduled_run(cid, aid, scheduled_run_id):
            sched_runs = db.get_scheduled_run_by_scheduler_id(cid, aid, scheduled_run_id)
            if len(sched_runs) == 0:
                logging.warning(
                    "Received trigger scheduled run request for scheduled_run_id '%s' but cannot find corresponding run.",
                    scheduled_run_id,
                )
                return util.error("")
            errors = 0
            for sched_run in sched_runs:
                if sched_run["status"] != ScheduledRunStatus.SCHEDULED:
                    logging.warning(
                        "Received trigger scheduled run for _id '%s' but this run has status '%s', which is not 'scheduled'.",
                        str(sched_run["_id"]),
                        sched_run["status"],
                    )
                    errors += 1

                # If roster is not provided, use course roster
                if sched_run["roster"] is None:
                    course = db.get_course(cid)
                    if course is None:
                        errors += 1
                    netids = course["student_ids"]
                # If a roster is provided, use it
                else:
                    netids = sched_run["roster"]

                # Start broadway grading run
                bw_run_id = jenkins_api.start_grading_run(
                    cid, aid, netids, sched_run["due_time"], True, None
                )
                if bw_run_id is None:
                    logging.warning("Failed to trigger run with broadway")
                    db.update_scheduled_run_status(
                        sched_run["_id"], ScheduledRunStatus.FAILED
                    )
                    errors += 1
                else:
                    db.update_scheduled_run_status(sched_run["_id"], ScheduledRunStatus.RAN)
                    db.update_scheduled_run_bw_run_id(sched_run["_id"], bw_run_id)
            if errors > 0:
                return util.error("")
            return util.success("")
