from flask import render_template, abort, request, jsonify
from http import HTTPStatus
import json, re

from src import db, util, auth, bw_api
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
            return jsonify(admin_ids=course['admin_ids'], staff_ids=course['staff_ids'], user=netid)

        @blueprint.route("/staff/course/<cid>/student_roster", methods=["GET"])
        @auth.require_auth
        @auth.require_admin_status
        def get_course_student_roster(netid, cid):
            course = db.get_course(cid)
            return jsonify(course['student_ids'])

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
            new_student_id = request.form.get('netid').lower()
            if new_student_id is None:
                return util.error("Cannot find netid field")
            if not util.is_valid_netid(new_student_id):
                return util.error(f"Poorly formatted NetID: '{new_student_id}'")
            result = db.add_student_to_course(cid, str(new_student_id))
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
            netids = file_content.strip().lower().split('\n')
            for i, student_id in enumerate(netids):
                if not util.is_valid_netid(student_id):
                    return util.error(f"Poorly formatted NetID on line {i + 1}: '{student_id}'")

            result = db.overwrite_student_roster(cid, netids)
            if none_modified(result):
                return util.error("The new roster is the same as the current one.")
            return util.success("Successfully updated roster.")

        @blueprint.route("/staff/course/<cid>/add_assignment/", methods=["POST"])
        @auth.require_auth
        @auth.require_admin_status
        def add_assignment(netid, cid):
            missing = util.check_missing_fields(request.form,
                                                *["aid", "max_runs", "quota", "start", "end", "config", "visibility"])
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
                db.add_extension(cid, aid, student_netid, max_runs, start, end)
            return util.success("")
