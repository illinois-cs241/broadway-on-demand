from flask_pymongo import PyMongo, ASCENDING, DESCENDING

mongo = PyMongo()


class Quota:
	# Gives students max_runs grading runs per day, resetting at midnight in the config-specified timezone. Runs do not
	# carry over between days.
	DAILY = "daily"

	# Gives students max_runs grading runs over the entire assignment period.
	TOTAL = "total"

	@classmethod
	def is_valid(cls, quota):
		return quota in [cls.DAILY, cls.TOTAL]


def init(app):
	mongo.init_app(app)


def get_user(netid):
	"""
	Get a user.
	:param netid: a user's NetID.
	:return: a user, or None if the NetID does not exist.
	"""
	return mongo.db.users.find_one({"_id": netid})


def set_user_access_token(netid, access_token):
	"""
	Updates the access token for the user with the given NetID, or adds a new user with the given NetID and access token
	if the NetID does not exist.
	:param netid: a user's NetID.
	:param access_token: a GitHub Enterprise access token for the user.
	"""
	mongo.db.users.update({"_id": netid}, {"access_token": access_token}, upsert=True)


def get_courses_for_student(netid):
	courses = mongo.db.courses.find({"student_ids": netid})
	return list(courses)


def get_courses_for_staff(netid):
	courses = mongo.db.courses.find({"staff_ids": netid})
	return list(courses)


def get_course(cid):
	return mongo.db.courses.find_one({"_id": cid})


def get_assignments_for_course(cid):
	return list(mongo.db.assignments.find({"course_id": cid}))


def get_assignment(cid, aid):
	return mongo.db.assignments.find_one({"course_id": cid, "assignment_id": aid})


def add_assignment(cid, aid, max_runs, quota, start, end):
	"""
	Add a new assignment.
	:param cid: a course ID.
	:param aid: a new, unique assignment ID.
	:param max_runs: the maximum number of grading runs for each student.
	:param quota: a quota type as defined in Quota.
	:param start: a UNIX timestamp specifying the start of the grading period.
	:param end: a UNIX timestamp specifying the end of the grading period.
	"""
	if quota not in [Quota.DAILY, Quota.TOTAL]:
		raise RuntimeError("Invalid quota type for assignment.")
	mongo.db.assignments.insert_one(
		{"course_id": cid, "assignment_id": aid, "max_runs": max_runs, "quota": quota, "start": start, "end": end})


def get_assignment_runs_for_student(cid, aid, netid):
	"""
	Get a student's runs for a specified course and assignment.
	:param cid: a course ID.
	:param aid: an assignment ID.
	:param netid: the student's NetID.
	:return: a list of matching runs, sorted by most recent to least recent.
	"""
	return list(mongo.db.runs.find({"course_id": cid, "assignment_id": aid, "netid": netid}).sort("timestamp", DESCENDING))


def get_assignment_runs(cid, aid):
	"""
	Get all runs for a specified course and assignment, grouped by student. E.g.:
	[
		{ _id: "netid1", runs: [ { _id: "run_id_1", timestamp: 123 }, ... ] },
		...
	]
	:param cid: a course ID.
	:param aid: an assignment ID.
	:return: a list of objects, each containing a list of runs for a single student.
	"""
	return mongo.db.runs.aggregate([
		{"$match": {"course_id": cid, "assignment_id": aid}},
		{"$group": {"_id": "$netid", "runs": {"$addToSet": {"_id": "$_id", "timestamp": "$timestamp"}}}},
		{"$sort": {"_id": 1}}
	])


def add_grading_run(cid, aid, netid, timestamp, run_id):
	"""
	Add a new grading run.
	:param cid: a course ID.
	:param aid: an assignment ID.
	:param netid: a student's NetID.
	:param timestamp: a UNIX timestamp for this run.
	:param run_id: the run ID received from Broadway API. Used to retrieve status.
	"""
	mongo.db.runs.insert_one({"_id": run_id, "course_id": cid, "assignment_id": aid, "netid": netid, "timestamp": timestamp})


def get_grading_run(run_id):
	return mongo.db.runs.find_one({"_id": run_id})
