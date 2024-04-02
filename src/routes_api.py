import logging
from flask import request
from http import HTTPStatus
from functools import wraps
import json

from src import db, util, auth, bw_api
from src.sched_api import ScheduledRunStatus, schedule_run, update_scheduled_run
from src.common import verify_student

MIN_PREDEADLINE_RUNS = 1  # Minimum pre-deadline runs for every assignment


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
        @blueprint.route("/api/<cid>/<aid>/add_extension", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def add_extension(cid, aid):
            form = request.json
            
            assignment = db.get_assignment(cid, aid)
            if not assignment:
                return util.error("Invalid course or assignment. Please try again.")
            
        
            missing = util.check_missing_fields(form, "netids", "max_runs", "start", "end")
            if missing:
                return util.error(f"Extension missing fields {', '.join(missing)}. Please try again.")

            student_netids = form["netids"].replace(" ", "").lower().split(",")
            for student_netid in student_netids:
                if not util.valid_id(student_netid) or not verify_student(student_netid, cid):
                    return util.error(f"Invalid or non-existent student NetID: {student_netid}")

            try:
                max_runs = int(form["max_runs"])
                if max_runs < 1:
                    return util.error("Max Runs must be a positive integer.")
            except ValueError:
                return util.error("Max Runs must be a positive integer.")

            print(form["start"], form["end"])

            start = util.parse_form_datetime(form["start"])
            if not start:
                return util.error("Failed to parse timestamp")
            start = start.timestamp()
            end = util.parse_form_datetime(form["end"])
            if not end:
                return util.error("Failed to parse timestamp")
            end = end.timestamp()
            if start >= end:
                return util.error("Start must be before End")

            ext_res = db.add_extension(cid, aid, ','.join(student_netids), max_runs, start, end)
            if not ext_res.acknowledged:
                return util.error("Failed to add extension to db")
            
            form = request.json
            run_id = db.generate_new_id()

            # Add scheduled run if specified in query
            if request.args.get("add_run"):
                msg, status = add_or_edit_scheduled_run(cid, aid, run_id, form, None)
                if status != HTTPStatus.OK:
                    # Rollback changes to db
                    db.delete_extension(ext_res.inserted_id)
                    return util.error(msg)
            return util.success("Successfully uploaded extension", HTTPStatus.OK)
        
        @blueprint.route("/api/<cid>/add_assignment", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def api_add_assignment(cid):
            form = request.json
            missing = util.check_missing_fields(form,
                                                *["aid", "max_runs", "quota", "start", "end", "config", "visibility"])
            if missing:
                return util.error(f"Missing fields ({', '.join(missing)}).")

            aid = form["aid"]
            if not util.valid_id(aid):
                return util.error("Invalid Assignment ID. Allowed characters: a-z A-Z _ - .")

            new_assignment = db.get_assignment(cid, aid)
            if new_assignment and not request.args.get('overwrite', False):
                return util.error("Assignment ID already exists.")

            try:
                max_runs = int(form["max_runs"])
                if max_runs < MIN_PREDEADLINE_RUNS:
                    return util.error(f"Max Runs must be at least {MIN_PREDEADLINE_RUNS}.")
            except ValueError:
                return util.error("Max Runs must be a positive integer.")

            quota = form["quota"]
            if not db.Quota.is_valid(quota):
                return util.error("Quota Type is invalid.")

            start = util.parse_form_datetime(form["start"])
            end = util.parse_form_datetime(form["end"])
            if start is None or end is None:
                return util.error("Missing or invalid Start or End.")
            start = start.timestamp()
            end = end.timestamp()
            if start >= end:
                return util.error("Start must be before End.")

            try:
                config = form["config"]
                if not isinstance(config, dict):
                    config = json.loads(config)
                msg = bw_api.set_assignment_config(cid, aid, config)

                if msg:
                    return util.error(f"Failed to add assignment to Broadway: {msg}")
            except json.decoder.JSONDecodeError:
                return util.error("Failed to decode config JSON")

            visibility = form["visibility"]

            if new_assignment:
                db.update_assignment(cid, aid, max_runs, quota, start, end, visibility)
            else:
                db.add_assignment(cid, aid, max_runs, quota, start, end, visibility)
            msg = "Successfully added assignment." if not new_assignment else \
                "Successfully updated assignment."
            return util.success(msg, HTTPStatus.OK)
        
        def add_or_edit_scheduled_run(cid, aid, run_id, form, scheduled_run_id):
            # course and assignment name validation
            course = db.get_course(cid)
            assignment = db.get_assignment(cid, aid)
            if course is None or assignment is None:
                return util.error("Could not find assignment", HTTPStatus.NOT_FOUND)

            # form validation
            missing = util.check_missing_fields(form, "run_time", "due_time", "name", "config")
            if missing:
                return util.error(f"Missing fields ({', '.join(missing)}).")
            run_time = util.parse_form_datetime(form["run_time"]).timestamp()
            if run_time is None:
                return util.error("Missing or invalid run time.")
            if run_time <= util.now_timestamp():
                return util.error("Run time must be in the future.")
            due_time = util.parse_form_datetime(form["due_time"]).timestamp()
            if due_time is None:
                return util.error("Missing or invalid due time.")
            if "roster" not in form or not form["roster"]:
                roster = None
            else:
                roster = form["roster"].replace(" ", "").lower().split(",")
                for student_netid in roster:
                    if not util.valid_id(student_netid) or not verify_student(student_netid, cid):
                        return util.error(f"Invalid or non-existent student NetID: {student_netid}")
            try:
                config = form["config"]
                if not isinstance(config, dict):
                    config = json.loads(config)
                msg = bw_api.set_assignment_config(cid, f"{aid}_{run_id}", config)
                if msg:
                    return util.error(f"Failed to upload config to Broadway: {msg}")
            except json.decoder.JSONDecodeError:
                return util.error("Failed to decode config JSON")

            # Schedule a new run with scheduler
            if scheduled_run_id is None:
                scheduled_run_id = schedule_run(run_time, cid, aid)
                if scheduled_run_id is None:
                    return util.error("Failed to schedule run with scheduler")
            # Or if the run was already scheduled, update the time
            else:
                if not update_scheduled_run(scheduled_run_id, run_time):
                    return util.error("Failed to update scheduled run time with scheduler")

            assert scheduled_run_id is not None

            if not db.add_or_update_scheduled_run(run_id, cid, aid, run_time, due_time, roster, form["name"], scheduled_run_id):
                return util.error("Failed to save the changes, please try again.")
            return util.success("Successfully scheduled run.", HTTPStatus.OK)
        
        @blueprint.route("/api/<cid>/<aid>/schedule_run", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def api_add_scheduled_run(cid, aid):
            # generate new id for this scheduled run
            form = request.json
            run_id = db.generate_new_id()
            return add_or_edit_scheduled_run(cid, aid, run_id, form, None)

        @blueprint.route("/api/<cid>/<aid>/schedule_runs", methods=["POST"])
        @auth.require_course_auth
        @auth.require_admin_status
        def api_add_scheduled_runs(cid, aid):
            form = request.json
            # generate new id for this scheduled run
            missing = util.check_missing_fields(form, "runs")
            if missing:
                return util.error(f"Missing fields {', '.join(missing)}")
            # TODO: there's probably a better way to do this
            print(form["runs"])
            print(type(form["runs"]))
            if not isinstance(form["runs"], list):
                return util.error("runs field must be a list of run configs!")
            for run_config in form["runs"]:
                run_id = db.generate_new_id()
                retval = add_or_edit_scheduled_run(cid, aid, run_id, run_config, None)
                # TODO: There should be a better distinction between good and bad responses
                if retval[1] != HTTPStatus.OK:
                    return retval
            return util.success("Successfully scheduled runs", HTTPStatus.OK)