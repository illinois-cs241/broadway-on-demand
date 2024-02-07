import logging
from flask import request
from http import HTTPStatus

from src import db, util, auth, bw_api
from src.sched_api import ScheduledRunStatus
from src.common import verify_student

class ApiRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/api/<cid>/update_roster", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def admin_update_roster(cid):
            netids = request.json["roster"].strip().lower().split("\n")

            for i, student_id in enumerate(netids):
                if not util.is_valid_netid(student_id):
                    return util.error(f"Poorly formatted NetID on line {i + 1}: '{student_id}'")

            db.overwrite_student_roster(cid, netids)
            return util.success("Successfully updated roster.", HTTPStatus.OK)

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
        
        # Want to avoid stuff like this, with overlaps in function definitions
        # Best way is to consider an AdminOperations class and have AdminRoutes and APIRoutes
        # use the functionality defined in there, instead of whatever I did with AdminRoutes currently
        @blueprint.route("/api/<cid>/add_extensions", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def add_extensions(netid, cid, aid):
            assignment = db.get_assignment(cid, aid)
            if not assignment:
                return util.error("Invalid course or assignment. Please try again.")
            
            if util.check_missing_fields(request.json, "extensions"):
                return util.error("Missing fields. Please try again.")
            
            for ext_json in request.json:
                if util.check_missing_fields(ext_json, "netids", "max_runs", "start", "end"):
                    return util.error("Missing fields. Please try again.")

                student_netids = ext_json["netids"].replace(" ", "").lower().split(",")
                for student_netid in student_netids:
                    if not util.valid_id(student_netid) or not verify_student(student_netid, cid):
                        return util.error(f"Invalid or non-existent student NetID: {student_netid}")

                try:
                    max_runs = int(ext_json["max_runs"])
                    if max_runs < 1:
                        return util.error("Max Runs must be a positive integer.")
                except ValueError:
                    return util.error("Max Runs must be a positive integer.")

                start = util.parse_form_datetime(ext_json["start"]).timestamp()
                end = util.parse_form_datetime(ext_json["end"]).timestamp()
                if start >= end:
                    return util.error("Start must be before End.")

                for student_netid in student_netids:
                    db.add_extension(cid, aid, student_netid, max_runs, start, end)
            return util.success("")
        
