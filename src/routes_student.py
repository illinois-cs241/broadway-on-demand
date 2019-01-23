from flask import render_template, redirect, request, abort

from src import bw_api, auth, util, db
from src.common import verify_student, verify_staff, in_grading_period, get_remaining_runs
from src.config import TZ


class StudentRoutes:
	def __init__(self, app):
		@app.route("/student/", methods=["GET"])
		@auth.require_auth
		def student_home(netid):
			courses = db.get_courses_for_student(netid)
			return render_template("student/home.html", netid=netid, courses=courses)

		@app.route("/student/course/<cid>/", methods=["GET"])
		@auth.require_auth
		def student_get_course(netid, cid):
			if not verify_student(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignments = db.get_assignments_for_course(cid)
			return render_template("student/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ))

		@app.route("/student/course/<cid>/<aid>/", methods=["GET"])
		@auth.require_auth
		def student_get_assignment(netid, cid, aid):
			if not verify_student(netid, cid):
				return abort(403)

			error = None
			if "error" in request.args:
				error_code = request.args["error"]
				if error_code == "grading_period":
					error = "Error: Not in grading period."
				elif error_code == "no_runs":
					error = "Error: No grading runs available."
				elif error_code == "failure":
					error = "Error: Failed to start grading run."

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			runs = db.get_assignment_runs_for_student(cid, aid, netid)
			now = util.now_timestamp()

			if not in_grading_period(assignment, now):
				available_runs = 0
			else:
				available_runs = get_remaining_runs(assignment, runs, now)

			if verify_staff(netid, cid):
				available_runs = max(available_runs, 1)

			return render_template("student/assignment.html", netid=netid, course=course, assignment=assignment, runs=runs, available_runs=available_runs, tzname=str(TZ), error=error)

		@app.route("/student/course/<cid>/<aid>/", methods=["POST"])
		@auth.require_auth
		def student_grade_assignment(netid, cid, aid):
			if not verify_student(netid, cid):
				return abort(403)

			assignment = db.get_assignment(cid, aid)
			runs = db.get_assignment_runs_for_student(cid, aid, netid=netid)
			now = util.now_timestamp()

			if not verify_staff(netid, cid):
				# not a staff member; perform student quota checks
				if not in_grading_period(assignment, now):
					return redirect("/student/course/%s/%s/?error=grading_period" % (cid, aid))
				elif get_remaining_runs(assignment, runs, now) <= 0:
					return redirect("/student/course/%s/%s/?error=no_runs" % (cid, aid))

			run_id = bw_api.start_grading_run(cid, aid, netid, now)
			if run_id is None:
				return redirect("/student/course/%s/%s/?error=failure" % (cid, aid))

			db.add_grading_run(cid, aid, netid, now, run_id)
			return redirect("/student/course/%s/%s/" % (cid, aid))
