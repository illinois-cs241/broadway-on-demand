from flask import render_template, request, abort

from src import db, util, auth, bw_api
from src.config import TZ
from src.common import verify_staff, verify_admin, verify_student


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

			netids = request.form["netids"].replace(" ", "").split(",")
			for netid in netids:
				if not util.valid_id(netid) or not verify_student(netid, cid):
					return err("Invalid or non-existent student NetID: %s" % netid)

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

			for netid in netids:
				db.add_extension(cid, aid, netid, max_runs, start, end)
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
