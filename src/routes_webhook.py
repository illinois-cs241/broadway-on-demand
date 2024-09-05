from http import HTTPStatus
from src import bw_api, auth, util, db
from flask import jsonify, request

def validate_student_enrollment(cid, aid, netid):
	student_courses = db.get_courses_for_student(netid)
	found_course = False
	for item in student_courses:
		if item['_id'] == cid:
			found_course = True
			break
	if not found_course:
		return False, "Student is not enrolled in this course or this student does not exist."
	course_assignments = db.get_assignments_for_course(cid=cid)
	found = False
	for assignment in course_assignments:
		if assignment['assignment_id'] == aid:
			found = True
			break
	if not found:
		return False, "Assignment does not exist in course."
	return True, "Student validated."

class WebhookRoutes:
	def __init__(self, blueprint):
		@blueprint.route("/webhook/healthz", methods=["GET"])
		@util.disable_in_maintenance_mode
		@auth.require_webhook_auth
		def webhook_home():
			return jsonify({"message": "Webhook is UP"}), HTTPStatus.OK

		@blueprint.route("/webhook/course/<cid>/<aid>/<netid>/run", methods=["POST"])
		@util.disable_in_maintenance_mode
		@auth.require_webhook_auth
		def webhook_grade_assignment(cid, aid, netid):
			verified, message = validate_student_enrollment(cid, aid, netid)
			if not verified:
				return jsonify({"message": message})
			now = util.now_timestamp()
			now_rounded = util.timestamp_round_up_minute(now)
			run_id = bw_api.start_grading_run(cid, aid, [netid], now_rounded)
			if run_id is None:
				return jsonify({"message": "Failed to start grading job."}), HTTPStatus.INTERNAL_SERVER_ERROR
			db.add_grading_run(cid, aid, netid, now, run_id, extension_used=None)
			return jsonify({"netid": netid, "cid": cid, "aid": aid, "run_id": run_id}), HTTPStatus.CREATED
