from flask import request
from src.config import SYSTEM_API_TOKEN
from src import db

class SystemRoutes:
	def __init__(self, app):
		@app.route("/system/feedback/", methods=["POST"])
		def system_feedback():
			if request.headers.get("Authorization") != ("Bearer %s" % SYSTEM_API_TOKEN):
				return "Unauthorized", 401
			data = request.json()
			if "run_id" not in data or "feedback" not in data:
				return "Missing 'run_id' or 'feedback' fields.", 400

