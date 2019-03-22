from subprocess import check_output, CalledProcessError

from flask import render_template, request, abort, jsonify

import json
from json.decoder import JSONDecodeError

from config import TZ
from src import db, util, auth, bw_api
from src.common import verify_staff, verify_admin, verify_student


class StaffRoutes:
	def __init__(self, blueprint):
		@blueprint.route("/staff/", methods=["GET"])
		@auth.require_auth
		def staff_home(netid):
			courses = db.get_courses_for_staff(netid)
			version_code = 'unknown'
			try:
				git_hash = check_output('git rev-parse --short=8 HEAD'.split(' ')).decode('utf-8')
				if len(git_hash) >= 8:
					version_code = git_hash[0:8]
			except CalledProcessError:
				pass
			return render_template("staff/home.html", netid=netid, courses=courses, version_code=version_code)

		@blueprint.route("/staff/course/<cid>/", methods=["GET"])
		@auth.require_auth
		def staff_get_course(netid, cid):
			if not verify_staff(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignments = list(db.get_assignments_for_course(cid))
			is_admin = verify_admin(netid, cid)
			return render_template("staff/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ), is_admin=is_admin, error=None)

		@blueprint.route("/staff/course/<cid>/<aid>/", methods=["POST"])
		@auth.require_auth
		def staff_add_assignment(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			def err(msg):
				return msg, 400

			missing = util.check_missing_fields(request.form, *["max_runs", "quota", "start", "end", "config"])
			if missing:
				return err("Missing fields (%s)." % (", ".join(missing)))

			if not util.valid_id(aid):
				return err("Invalid Assignment ID. Allowed characters: a-z A-Z _ - .")

			new_assignment = db.get_assignment(cid, aid)
			if new_assignment:
				return err("Assignment ID already exists.")

			try:
				max_runs = int(request.form["max_runs"])
				if max_runs < 1:
					return err("Max Runs must be a positive integer.")
			except ValueError:
				return err("Max Runs must be a positive integer.")

			quota = request.form["quota"]
			if not db.Quota.is_valid(quota):
				return err("Quota Type is invalid.")

			start = util.parse_form_datetime(request.form["start"]).timestamp()
			end = util.parse_form_datetime(request.form["end"]).timestamp()
			if start is None or end is None:
				return err("Missing or invalid Start or End.")
			if start >= end:
				return err("Start must be before End.")

			try:
				config = json.loads(request.form["config"])
				msg = bw_api.set_assignment_config(cid, aid, config)

				if msg:
					return err("Failed to add assignment to Broadway: {}".format(msg))
			except JSONDecodeError:
				return err("Failed to decode config JSON")

			db.add_assignment(cid, aid, max_runs, quota, start, end)
			return "", 204

		@blueprint.route("/staff/course/<cid>/<aid>/", methods=["GET"])
		@auth.require_auth
		def staff_get_assignment(netid, cid, aid):
			if not verify_staff(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			student_runs = list(db.get_assignment_runs(cid, aid))
			is_admin = verify_admin(netid, cid)

			assignment_config = json.dumps(bw_api.get_assignment_config(cid, aid))

			return render_template("staff/assignment.html", netid=netid, course=course,
								   assignment=assignment, assignment_config=assignment_config,
								   student_runs=student_runs, tzname=str(TZ), is_admin=is_admin)

		@blueprint.route("/staff/course/<cid>/<aid>/edit/", methods=["POST"])
		@auth.require_auth
		def staff_edit_assignment(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			if course is None or assignment is None:
				return abort(404)

			def err(msg):
				return msg, 400

			missing = util.check_missing_fields(request.form, *["max_runs", "quota", "start", "end"])
			if missing:
				return err("Missing fields (%s)." % (", ".join(missing)))

			try:
				max_runs = int(request.form["max_runs"])
				if max_runs < 1:
					return err("Max Runs must be a positive integer.")
			except ValueError:
				return err("Max Runs must be a positive integer.")

			quota = request.form["quota"]
			if not db.Quota.is_valid(quota):
				return err("Quota Type is invalid.")

			start = util.parse_form_datetime(request.form["start"]).timestamp()
			end = util.parse_form_datetime(request.form["end"]).timestamp()
			if start is None or end is None:
				return err("Missing or invalid Start or End.")
			if start >= end:
				return err("Start must be before End.")

			try:
				config = json.loads(request.form["config"])
				msg = bw_api.set_assignment_config(cid, aid, config)

				if msg:
					return err("Failed to add assignment to Broadway: {}".format(msg))
			except JSONDecodeError:
				return err("Failed to decode config JSON")

			if not db.update_assignment(cid, aid, max_runs, quota, start, end):
				return err("Save failed or no changes were made.")
			return "", 204

		@blueprint.route("/staff/course/<cid>/<aid>/extensions/", methods=["GET"])
		@auth.require_auth
		def staff_get_extensions(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			extensions = list(db.get_extensions(cid, aid))
			for ext in extensions:
				ext["_id"] = str(ext["_id"])
			return jsonify(extensions), 200

		@blueprint.route("/staff/course/<cid>/<aid>/extensions/", methods=["POST"])
		@auth.require_auth
		def staff_add_extension(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			def err(msg):
				return msg, 400

			assignment = db.get_assignment(cid, aid)
			if not assignment:
				return err("Invalid course or assignment. Please try again.")

			if util.check_missing_fields(request.form, "netids", "max_runs", "start", "end"):
				return err("Missing fields. Please try again.")

			student_netids = request.form["netids"].replace(" ", "").split(",")
			for student_netid in student_netids:
				if not util.valid_id(student_netid) or not verify_student(student_netid, cid):
					return err("Invalid or non-existent student NetID: %s" % student_netid)

			try:
				max_runs = int(request.form["max_runs"])
				if max_runs < 1:
					return err("Max Runs must be a positive integer.")
			except ValueError:
				return err("Max Runs must be a positive integer.")

			start = util.parse_form_datetime(request.form["start"]).timestamp()
			end = util.parse_form_datetime(request.form["end"]).timestamp()
			if start >= end:
				return err("Start must be before End.")

			for student_netid in student_netids:
				db.add_extension(cid, aid, student_netid, max_runs, start, end)
			return "", 204

		@blueprint.route("/staff/course/<cid>/<aid>/<run_id>/status/", methods=["GET"])
		@auth.require_auth
		def staff_get_run_status(netid, cid, aid, run_id):
			if not verify_staff(netid, cid):
				return abort(403)

			status = bw_api.get_grading_run_status(cid, aid, run_id)
			if status:
				return status
			return "", 400
