from datetime import datetime, timedelta

from flask import render_template, request, abort, jsonify

from src import db, util, auth, bw_api
from src.config import TZ
from src.common import verify_staff, verify_admin, verify_student, get_available_runs


class StaffRoutes:
	def __init__(self, app):
		@app.route("/staff/", methods=["GET"])
		@auth.require_auth
		def staff_home(netid):
			courses = db.get_courses_for_staff(netid)
			return render_template("staff/home.html", netid=netid, courses=courses)

		@app.route("/staff/course/<cid>/", methods=["GET"])
		@auth.require_auth
		def staff_get_course(netid, cid):
			if not verify_staff(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignments = list(db.get_assignments_for_course(cid))
			is_admin = verify_admin(netid, cid)
			return render_template("staff/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ), is_admin=is_admin, error=None)

		@app.route("/staff/course/<cid>/<aid>/", methods=["POST"])
		@auth.require_auth
		def staff_add_assignment(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			def err(msg):
				return msg, 400

			missing = util.check_missing_fields(request.form, *["max_runs", "quota", "start", "end"])
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

			db.add_assignment(cid, aid, max_runs, quota, start, end)
			return "", 204

		@app.route("/staff/course/<cid>/<aid>/", methods=["GET"])
		@auth.require_auth
		def staff_get_assignment(netid, cid, aid):
			if not verify_staff(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			student_runs = list(db.get_assignment_runs(cid, aid))
			is_admin = verify_admin(netid, cid)
			return render_template("staff/assignment.html", netid=netid, course=course, assignment=assignment, student_runs=student_runs, tzname=str(TZ), is_admin=is_admin)

		@app.route("/staff/course/<cid>/<aid>/extensions/", methods=["GET"])
		@auth.require_auth
		def staff_get_extensions(netid, cid, aid):
			if not verify_staff(netid, cid) or not verify_admin(netid, cid):
				return abort(403)

			extensions = list(db.get_extensions(cid, aid))
			for ext in extensions:
				ext["_id"] = str(ext["_id"])
			return jsonify(extensions), 200

		@app.route("/staff/course/<cid>/<aid>/extensions/", methods=["POST"])
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

		@app.route("/staff/course/<cid>/<aid>/<run_id>/status/", methods=["GET"])
		@auth.require_auth
		def staff_get_run_status(netid, cid, aid, run_id):
			if not verify_staff(netid, cid):
				return abort(403)

			status = bw_api.get_grading_run_status(cid, aid, run_id)
			if status:
				return status
			return "", 400

		@app.route("/staff/course/<cid>/<aid>/unused")
		def staff_start_unused_grading_run(cid, aid):
			"""
			This endpoint, given cid and aid, checks for unused grading runs of all students in the course for
			the previous day at 23:59:59. If a student didn't use an autograder run the previous day, an autograder
			run is triggered for them.
			:param cid: a course ID
			:param aid: an assignment ID
			:return: HTTP 204 if request succeeded, 403 if unsafe
			"""
			# We expect this endpoint to be used only from localhost.
			if request.headers.get("X-Forwarded-For"):
				# Request originated from nginx. This is unsafe. Abort.
				return abort(403)

			# Calculate check_time which for 12 am deadlines is the previous day @ 23:59:59
			now = datetime.now()
			today_midnight = datetime(now.year, now.month, now.day)		# current day midnight
			check_time = today_midnight - timedelta(seconds=1)			# previous day 23:59:59
			check_timestamp = check_time.timestamp()

			# Get list of students in the course, and check for unused grading runs
			student_ids = list(db.get_students_for_course(cid))
			for netid in student_ids:
				num_available_runs = get_available_runs(cid, aid, netid, check_timestamp)

				if num_available_runs > 0:
					# If the student has an available run, use it
					run_id = bw_api.start_grading_run(cid, aid, netid, check_timestamp)
					if run_id is None:
						print("Failed to start unused grading run for cid: %s, aid: %s, netid: %s" % (cid, aid, netid))
						continue

					db.add_grading_run(cid, aid, netid, check_timestamp, run_id, extension_used=None)

			return "", 204
