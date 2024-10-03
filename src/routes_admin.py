import csv
from datetime import timedelta
from xxlimited import new
from flask import render_template, abort, request, jsonify
from http import HTTPStatus
import json, re

from src import db, util, auth, bw_api, sched_api
from src.common import verify_staff, verify_admin, verify_student

MIN_PREDEADLINE_RUNS = 1  # Minimum pre-deadline runs for every assignment

class AdminRoutes:
    def __init__(self, blueprint):
        def none_modified(result):
            """
            Return true if the database was NOT modified as a result of the API call.
            :param result: A WriteResult returned by mongo db update calls
            """
            return result["nModified"] == 0

        @blueprint.route("/staff/course/<cid>/roster", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def get_course_roster_page(netid, cid):
            course = db.get_course(cid)
            return render_template("staff/roster.html", netid=netid, course=course)

        @blueprint.route("/staff/course/<cid>/staff_roster", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def get_course_staff_roster(netid, cid):
            course = db.get_course(cid)
            
            staff = course["staff"]
            # get all admin_ids by filtering out all non-admins
            admin = dict(filter(lambda x : x[1].get("is_admin") == True, staff.items()))
            admin = list(admin.keys())
            # get the entire staff
            total_staff = list(staff.keys())
            
            return jsonify(admin_ids=admin, staff_ids=total_staff, user=netid)

        @blueprint.route("/staff/course/<cid>/student_roster", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def get_course_student_roster(netid, cid):
            course = db.get_course(cid)
            return jsonify(sorted(course['student_enhanced_mapping'], key=lambda d: d['name']))

        @blueprint.route("/staff/course/<cid>/add_staff", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def add_course_staff(netid, cid):
            new_staff_id = request.form.get('netid').lower()
            if new_staff_id is None:
                return util.error("Cannot find netid field")
            if not util.is_valid_netid(new_staff_id):
                return util.error(f"Poorly formatted NetID: '{new_staff_id}'")
            result = db.add_staff_to_course(cid, str(new_staff_id))
            if none_modified(result):
                return util.error(f"'{new_staff_id}' is already a course staff")
            return util.success(f"Successfully added {new_staff_id}")

        @blueprint.route("/staff/course/<cid>/remove_staff", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def remove_course_staff(netid, cid):
            staff_id = request.form.get('netid')
            result = db.remove_staff_from_course(cid, staff_id)
            if none_modified(result):
                return util.error(f"'{staff_id}' is not a staff")
            return util.success(f"Successfully removed '{staff_id}'")

        @blueprint.route("/staff/course/<cid>/promote_staff", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def promote_course_staff(netid, cid):
            staff_id = request.form.get('netid')
            if not verify_staff(staff_id, cid):
                return util.error(f"'{staff_id}' is not a staff")
            result = db.add_admin_to_course(cid, staff_id)
            if none_modified(result):
                return util.error(f"'{staff_id}' is already an admin")
            return util.success(f"Successfully made '{staff_id}' admin")

        @blueprint.route("/staff/course/<cid>/demote_admin", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def demote_course_admin(netid, cid):
            staff_id = request.form.get('netid')
            if not verify_staff(staff_id, cid) or not verify_admin(staff_id, cid):
                return util.error(f"'{staff_id}' is not a admin")
            db.remove_admin_from_course(cid, staff_id)
            return util.success(f"Successfully removed '{staff_id}' from admin")

        @blueprint.route("/staff/course/<cid>/add_student", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def add_course_student(netid, cid):
            semicolon_seperated = request.form.get('netid')
            try:
                new_student_id, new_student_uin, new_student_name = semicolon_seperated.split(";")
                new_student_id = new_student_id.lower()
            except Exception:
                return util.error("Cannot find all fields")
            if not util.is_valid_netid(new_student_id):
                return util.error(f"Poorly formatted NetID: '{new_student_id}'")
            if not util.is_valid_uin(new_student_uin):
                return util.error(f"Poorly formatted UIN: '{new_student_uin}'")
            result = db.add_student_to_course(cid, str(new_student_id), str(new_student_uin), str(new_student_name))
            if none_modified(result):
                return util.error(f"'{new_student_id}' is already a student")
            return util.success(f"Successfully added {new_student_id}")

        @blueprint.route("/staff/course/<cid>/remove_student", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def remove_course_student(netid, cid):
            student_id = request.form.get('netid')
            result = db.remove_student_from_course(cid, student_id)
            if none_modified(result):
                return util.error(f"'{student_id}' is not a student")
            return util.success(f"Successfully removed '{student_id}'")

        @blueprint.route("/staff/course/<cid>/upload_roster_file", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def upload_roster_file(netid, cid):
            file_content = request.form.get('content')
            reader = csv.DictReader(file_content.strip().split("\n"), dialect=csv.excel)

            students = []

            for i, row in enumerate(reader):
                netid, uin, name = row.get("Net ID"), row.get("UIN"), row.get("Name")
                
                if not util.is_valid_student(netid, uin, name):
                    return util.error(f"Invalid student on line {i + 1} ({row}): netid='{netid}', uin={uin}, name='{name}'")
                
                students.append((netid, uin, name))

            result = db.overwrite_student_roster(cid, students)
            if none_modified(result):
                return util.error("The new roster is the same as the current one.")
            return util.success("Successfully updated roster.")

        @blueprint.route("/staff/course/<cid>/add_assignment/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def add_assignment(netid, cid):
            missing = util.check_missing_fields(request.form,
                                                *["aid", "max_runs", "quota", "start", "end", "config", "visibility", "grading_config"])
            if missing:
                return util.error(f"Missing fields ({', '.join(missing)}).")

            aid = request.form["aid"]
            if not util.valid_id(aid):
                return util.error("Invalid Assignment ID. Allowed characters: a-z A-Z _ - .")

            new_assignment = db.get_assignment(cid, aid)
            if new_assignment:
                return util.error("Assignment ID already exists.")

            try:
                max_runs = int(request.form["max_runs"])
                if max_runs < MIN_PREDEADLINE_RUNS:
                    return util.error(f"Max Runs must be at least {MIN_PREDEADLINE_RUNS}.")
            except ValueError:
                return util.error("Max Runs must be a positive integer.")

            quota = request.form["quota"]
            if not db.Quota.is_valid(quota):
                return util.error("Quota Type is invalid.")

            start = util.parse_form_datetime(request.form["start"]).timestamp()
            end = util.parse_form_datetime(request.form["end"]).timestamp()
            run_start_str = (util.parse_form_datetime(request.form["end"]) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
            end_str = util.parse_form_datetime(request.form["end"]).strftime("%Y-%m-%dT%H:%M")
            run_id = db.generate_new_id()
            if start is None or end is None:
                return util.error("Missing or invalid Start or End.")
            if start >= end:
                return util.error("Start must be before End.")

            try:
                config = json.loads(request.form["config"])
                msg = bw_api.set_assignment_config(cid, aid, config)

                if msg:
                    return util.error(f"Failed to add assignment to Broadway: {msg}")
            except json.decoder.JSONDecodeError:
                return util.error("Failed to decode config JSON")

            visibility = request.form["visibility"]

            db.add_assignment(cid, aid, max_runs, quota, start, end, visibility)
            # Schedule Final Grading Run 
            schedule_result = add_or_edit_scheduled_run(cid, aid, run_id, {"run_time": run_start_str, "due_time": end_str, "name": "Final Grading Run", "config": request.form['grading_config']}, None)
            print("Add assignment - schedule result:", schedule_result, flush=True)
            db.pair_assignment_final_grading_run(cid, aid, str(run_id))
            return util.success("")

        @blueprint.route("/staff/course/<cid>/<aid>/edit/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def edit_assignment(netid, cid, aid):
            course = db.get_course(cid)
            assignment = db.get_assignment(cid, aid)
            if course is None or assignment is None:
                return abort(HTTPStatus.NOT_FOUND)

            missing = util.check_missing_fields(request.form, *["max_runs", "quota", "start", "end", "visibility"])
            if missing:
                return util.error(f"Missing fields ({', '.join(missing)}).")

            try:
                max_runs = int(request.form["max_runs"])
                if max_runs < MIN_PREDEADLINE_RUNS:
                    return util.error(f"Max Runs must be at least {MIN_PREDEADLINE_RUNS}.")
            except ValueError:
                return util.error("Max Runs must be a positive integer.")

            quota = request.form["quota"]
            if not db.Quota.is_valid(quota):
                return util.error("Quota Type is invalid.")

            start = util.parse_form_datetime(request.form["start"]).timestamp()
            end = util.parse_form_datetime(request.form["end"]).timestamp()
            if start is None or end is None:
                return util.error("Missing or invalid Start or End.")
            if start >= end:
                return util.error("Start must be before End.")

            try:
                config_str = request.form.get("config")

                if config_str is not None:  # skip update otherwise
                    config = json.loads(request.form["config"])
                    msg = bw_api.set_assignment_config(cid, aid, config)

                    if msg:
                        return util.error(f"Failed to update assignment config to Broadway: {msg}")
            except json.decoder.JSONDecodeError:
                return util.error("Failed to decode config JSON")

            visibility = request.form["visibility"]

            if not db.update_assignment(cid, aid, max_runs, quota, start, end, visibility):
                return util.error("Save failed or no changes were made.")
            return util.success("")
        
        @blueprint.route("/staff/course/<cid>/<aid>/delete/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def delete_assignment(netid, cid, aid):
            if not db.remove_assignment(cid, aid):
                return util.error("Assignment doesn't exist")
            return util.success("")

        @blueprint.route("/staff/course/<cid>/<aid>/extensions/", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_get_extensions(netid, cid, aid):
            extensions = list(db.get_extensions(cid, aid))
            for ext in extensions:
                ext["_id"] = str(ext["_id"])
            return util.success(jsonify(extensions), HTTPStatus.OK)

        @blueprint.route("/staff/course/<cid>/<aid>/extensions/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_add_extension(netid, cid, aid):
            assignment = db.get_assignment(cid, aid)
            if not assignment:
                return util.error("Invalid course or assignment. Please try again.")

            if util.check_missing_fields(request.form, "netids", "max_runs", "start", "end"):
                return util.error("Missing fields. Please try again.")

            student_netids = request.form["netids"].replace(" ", "").lower().split(",")
            for student_netid in student_netids:
                if not util.valid_id(student_netid) or not verify_student(student_netid, cid):
                    return util.error(f"Invalid or non-existent student NetID: {student_netid}")

            try:
                max_runs = int(request.form["max_runs"])
                if max_runs < 1:
                    return util.error("Max Runs must be a positive integer.")
            except ValueError:
                return util.error("Max Runs must be a positive integer.")

            start = util.parse_form_datetime(request.form["start"]).timestamp()
            end = util.parse_form_datetime(request.form["end"]).timestamp()
            if start >= end:
                return util.error("Start must be before End.")

            for student_netid in student_netids:
                end_str = util.parse_form_datetime(request.form["end"]).strftime("%Y-%m-%dT%H:%M")
                # avoid that weird race condition - start run 5 min after, but with a container due date of the original time
                ext_end = (util.parse_form_datetime(request.form["end"]) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
                run_id = db.generate_new_id()
                print("Schedule result:", add_or_edit_scheduled_run(cid, aid, run_id, {"run_time": ext_end, "due_time": end_str, "name": f"Extension Run - {student_netid}", "config": request.form['config'], "roster": student_netid}, None), flush=True)
                db.add_extension(cid, aid, student_netid, max_runs, start, end, run_id)
            return util.success("")
        
        @blueprint.route("/staff/course/<cid>/<aid>/extensions/", methods=["DELETE"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_delete_extension(netid, cid, aid):
            extension_id = request.form["_id"]
            delete_result = db.delete_extension(extension_id)

            if delete_result is None:
                return util.error("Invalid extension, please refresh the page.")
            if delete_result.deleted_count != 1:
                return util.error("Failed to delete extension.")

            return util.success("")

        def add_or_edit_scheduled_run(cid, aid, run_id, form, scheduled_run_id):
            # course and assignment name validation
            course = db.get_course(cid)
            assignment = db.get_assignment(cid, aid)
            if course is None or assignment is None:
                return abort(HTTPStatus.NOT_FOUND)

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
                config = json.loads(form["config"])
                msg = bw_api.set_assignment_config(cid, f"{aid}_{run_id}", config)
                if msg:
                    return util.error(f"Failed to upload config to Broadway: {msg}")
            except json.decoder.JSONDecodeError:
                return util.error("Failed to decode config JSON")

            # Schedule a new run with scheduler
            if scheduled_run_id is None:
                scheduled_run_id = sched_api.schedule_run(run_time, cid, aid)
                if scheduled_run_id is None:
                    return util.error("Failed to schedule run with scheduler")
            # Or if the run was already scheduled, update the time
            else:
                if not sched_api.update_scheduled_run(scheduled_run_id, run_time):
                    return util.error("Failed to update scheduled run time with scheduler")

            assert scheduled_run_id is not None

            if not db.add_or_update_scheduled_run(run_id, cid, aid, run_time, due_time, roster, form["name"], scheduled_run_id):
                return util.error("Failed to save the changes, please try again.")
            return util.success("")

        @blueprint.route("/staff/course/<cid>/<aid>/schedule_run/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_schedule_run(netid, cid, aid):
            # generate new id for this scheduled run
            run_id = db.generate_new_id()
            return add_or_edit_scheduled_run(cid, aid, run_id, request.form, None)

        @blueprint.route("/staff/course/<cid>/<aid>/schedule_run/<run_id>", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_edit_scheduled_run(netid, cid, aid, run_id):
            sched_run = db.get_scheduled_run(cid, aid, run_id)
            if sched_run is None:
                return util.error("Could not find this scheduled run. Please refresh and try again.")
            if sched_run["status"] != sched_api.ScheduledRunStatus.SCHEDULED:
                return util.error("Cannot edit past runs")
            scheduled_run_id = sched_run["scheduled_run_id"]
            return add_or_edit_scheduled_run(cid, aid, run_id, request.form, scheduled_run_id)

        @blueprint.route("/staff/course/<cid>/<aid>/schedule_run/<run_id>", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_get_scheduled_run(netid, cid, aid, run_id):
            sched_run = db.get_scheduled_run(cid, aid, run_id)
            if sched_run is None:
                return util.error("Cannot find scheduled run")
            del sched_run["_id"]
            return util.success(json.dumps(sched_run), 200)

        @blueprint.route("/staff/course/<cid>/<aid>/schedule_run/<run_id>", methods=["DELETE"])
        @auth.require_auth
        @auth.require_admin_status
        def staff_delete_scheduled_run(netid, cid, aid, run_id):
            sched_run = db.get_scheduled_run(cid, aid, run_id)
            if sched_run is None:
                return util.error("Cannot find scheduled run")
            sched_api.delete_scheduled_run(sched_run["scheduled_run_id"])
            if not db.delete_scheduled_run(cid, aid, run_id):
                return util.error("Failed to delete scheduled run. Please try again")
            return util.success("")

        
        