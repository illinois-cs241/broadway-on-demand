from flask import render_template, redirect, request, abort

from src import bw_api, auth, util, db
from src.common import verify_student, verify_staff, in_grading_period, get_available_runs, get_active_extensions
from src.config import TZ


class StudentRoutes:
	def __init__(self, blueprint):
		@blueprint.route("/student/", methods=["GET"])
		@auth.require_auth
		def student_home(netid):
			courses = db.get_courses_for_student(netid)
			return render_template("student/home.html", netid=netid, courses=courses)

		@blueprint.route("/student/course/<cid>/", methods=["GET"])
		@auth.require_auth
		def student_get_course(netid, cid):
			if not verify_student(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignments = db.get_assignments_for_course(cid)
			return render_template("student/course.html", netid=netid, course=course, assignments=assignments, tzname=str(TZ))

		@blueprint.route("/student/course/<cid>/<aid>/", methods=["GET"])
		@auth.require_auth
		def student_get_assignment(netid, cid, aid):
			if not verify_student(netid, cid):
				return abort(403)

			course = db.get_course(cid)
			assignment = db.get_assignment(cid, aid)
			runs = db.get_assignment_runs_for_student(cid, aid, netid)
			now = util.now_timestamp()

			num_available_runs = get_available_runs(cid, aid, netid, now)
			active_extensions, num_extension_runs = get_active_extensions(cid, aid, netid, now)

			if verify_staff(netid, cid):
				num_available_runs = max(num_available_runs, 1)

			return render_template("student/assignment.html", netid=netid, course=course, assignment=assignment, runs=runs, num_available_runs=num_available_runs, num_extension_runs=num_extension_runs, tzname=str(TZ))

		@blueprint.route("/student/course/<cid>/<aid>/run/", methods=["POST"])
		@auth.require_auth
		def student_grade_assignment(netid, cid, aid):
			if not verify_student(netid, cid):
				return abort(403)

			def err(msg):
				return msg, 400

			now = util.now_timestamp()
			now = util.timestamp_round_up_minute(now)

			ext_to_use = None

			if not verify_staff(netid, cid):
				# not a staff member; perform quota checks
				num_available_runs = get_available_runs(cid, aid, netid, now)
				active_extensions, num_extension_runs = get_active_extensions(cid, aid, netid, now)

				if num_available_runs + num_extension_runs <= 0:
					return err("No grading runs available.")
				if num_available_runs <= 0:
					# find the extension that is closest to expiration
					ext_to_use = min(active_extensions, key=lambda ext: ext["end"])

			run_id = bw_api.start_grading_run(cid, aid, netid, now)
			if run_id is None:
				return err("Failed to start grading run. Please try again.")

			db.add_grading_run(cid, aid, netid, now, run_id, extension_used=ext_to_use)
			return "", 204

		@blueprint.route("/student/course/<cid>/<aid>/<run_id>/status/", methods=["GET"])
		@auth.require_auth
		def student_get_run_status(netid, cid, aid, run_id):
			if not verify_student(netid, cid):
				return abort(403)

			status = bw_api.get_grading_run_status(cid, aid, run_id)
			if status:
				return status
			return "", 400
