from flask import render_template, request, redirect, abort

from src import db, util, auth, bw_api
from src.config import TZ
from src.common import verify_staff

import json

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
			assignments = db.get_assignments_for_course(cid)
			return render_template("staff/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ), error=None)

		@app.route("/staff/course/<cid>/", methods=["POST"])
		@auth.require_auth
		def staff_attempt_add_assignment(netid, cid):
			if not verify_staff(netid, cid):
				return abort(403)

			def err(msg):
				return render_template("staff/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ), error=msg)

			course = db.get_course(cid)
			assignments = db.get_assignments_for_course(cid)

			missing = util.check_missing_fields(request.form, *["aid", "max_runs", "quota", "start", "end", "grader_conf"])
			if missing:
				return err("Error: Missing fields (%s)" % (", ".join(missing)))

			aid = request.form["aid"]
			if not util.valid_id(aid):
				return err("Error: Invalid Assignment ID. Allowed characters: a-z A-Z _ - .")

			new_assignment = db.get_assignment(cid, request.form["aid"])
			if new_assignment:
				return err("Error: Assignment ID already exists.")

			try:
				max_runs = int(request.form["max_runs"])
				if max_runs < 1:
					return err("Error: Max Runs must be a positive integer.")
			except ValueError:
				return err("Error: Maximum Grading Runs must be a positive integer.")

			start = util.parse_form_datetime(request.form["start"]).timestamp()
			end = util.parse_form_datetime(request.form["end"]).timestamp()
			if start >= end:
				return err("Error: Start must be before End.")

			# add assignment to broadway
			grader_conf = request.form["grader_conf"]
			
			if not util.valid_json(grader_conf):
				return err("Error: Grader config is not a valid JSON object")

			if not bw_api.add_assignment(cid, request.form["aid"], json.loads(grader_conf)):
				return err("Error: Failed to add assignment")

			db.add_assignment(cid, request.form["aid"], max_runs, request.form["quota"], start, end)
			return redirect("/staff/course/%s/" % cid)

		@app.route("/staff/course/<cid>/<aid>/", methods=["GET"])
		@auth.require_auth
		def staff_get_assignment(netid, cid, aid):
			if not verify_staff(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			student_runs = db.get_assignment_runs(cid, aid)
			return render_template("staff/assignment.html", netid=netid, course=course, assignment=assignment, student_runs=student_runs, tzname=str(TZ))

		@app.route("/staff/course/<cid>/<aid>/<run_id>/status/", methods=["GET"])
		@auth.require_auth
		def staff_get_run_status(netid, cid, aid, run_id):
			if not verify_staff(netid, cid):
				return abort(403)

			status = bw_api.get_grading_run_status(cid, aid, run_id)
			if status:
				return status
			return "unknown; please try again"
