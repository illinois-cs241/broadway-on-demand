from flask import request

from config import SYSTEM_API_TOKEN


class SystemRoutes:
	def __init__(self, blueprint):
		@blueprint.route("/system/feedback/", methods=["POST"])
		def system_feedback():
			if request.headers.get("Authorization") != ("Bearer %s" % SYSTEM_API_TOKEN):
				return "Unauthorized", 401
			data = request.json()
			if "run_id" not in data or "feedback" not in data:
				return "Missing 'run_id' or 'feedback' fields.", 400

