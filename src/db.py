from flask_pymongo import PyMongo, ASCENDING, DESCENDING
from src import util

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


# Assignment visibility to students
class Visibility:
	HIDDEN = "hidden"
	VISIBLE = "visible"
	VISIBLE_FROM_START = "visible_from_start"  # visible from start date of the assignment


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
	mongo.db.users.update_one({"_id": netid}, {"$set": {"access_token": access_token}}, upsert=True)

def get_courses_for_student_or_staff(netid):
	student_course = get_courses_for_student(netid)
	staff_course = get_courses_for_staff(netid)
	for course in staff_course:
		if course not in student_course:
			student_course.append(course)
	return student_course


def get_courses_for_student(netid):
	courses = mongo.db.courses.find({"student_ids": netid})
	return list(courses)


def get_courses_for_staff(netid):
	courses = mongo.db.courses.find({"staff_ids": netid})
	return list(courses)


def get_course(cid):
	return mongo.db.courses.find_one({"_id": cid})


def add_staff_to_course(cid, new_staff_id):
	return mongo.db.courses.update({"_id": cid}, {"$addToSet": {"staff_ids": new_staff_id}})


def remove_staff_from_course(cid, staff_id):
	return mongo.db.courses.update({"_id": cid}, {
		"$pull": {
			"staff_ids": staff_id,
			"admin_ids": staff_id,
		}
	})


def add_student_to_course(cid, new_student_id):
	return mongo.db.courses.update({"_id": cid}, {"$addToSet": {"student_ids": new_student_id}})


def remove_student_from_course(cid, student_id):
	return mongo.db.courses.update({"_id": cid}, {"$pull": {"student_ids": student_id}})


def add_admin_to_course(cid, staff_id):
	return mongo.db.courses.update({"_id": cid}, {"$addToSet": {"admin_ids": staff_id}})


def remove_admin_from_course(cid, staff_id):
	return mongo.db.courses.update({"_id": cid}, {"$pull": {"admin_ids": staff_id}})


def overwrite_student_roster(cid, student_ids):
	return mongo.db.courses.update({"_id": cid}, {"$set": {"student_ids": student_ids}})


def get_assignments_for_course(cid, visible_only=False):
	if visible_only:
		now = util.now_timestamp()
		# if visible from start date, and start date has past
		visible_from_start_date = {
			"visibility": Visibility.VISIBLE_FROM_START,
			"start": {"$lte": now}
		}
		# if always visible
		visible_always = {
			"visibility": Visibility.VISIBLE
		}
		return list(mongo.db.assignments.find({"course_id": cid,"$or": [visible_from_start_date, visible_always]}))
	else:
		return list(mongo.db.assignments.find({"course_id": cid}))


def get_assignment(cid, aid):
	return mongo.db.assignments.find_one({"course_id": cid, "assignment_id": aid})


def add_assignment(cid, aid, max_runs, quota, start, end, visibility):
	"""
	Add a new assignment.
	:param cid: a course ID.
	:param aid: a new, unique assignment ID.
	:param max_runs: the maximum number of grading runs for each student.
	:param quota: a quota type as defined in Quota.
	:param start: a UNIX timestamp specifying the start of the grading period.
	:param end: a UNIX timestamp specifying the end of the grading period.
	:param visibility: a boolean value to indicate if the assignment is visible to students or not
	"""
	if quota not in [Quota.DAILY, Quota.TOTAL]:
		raise RuntimeError("Invalid quota type for assignment.")
	mongo.db.assignments.insert_one(
		{"course_id": cid, "assignment_id": aid, "max_runs": max_runs, "quota": quota, "start": start, "end": end, "visibility": visibility})


def update_assignment(cid, aid, max_runs, quota, start, end, visibility):
	if quota not in [Quota.DAILY, Quota.TOTAL]:
		raise RuntimeError("Invalid quota type for assignment.")
	res = mongo.db.assignments.update(
		{"course_id": cid, "assignment_id": aid},
		{"$set": {"max_runs": max_runs, "quota": quota, "start": start, "end": end, "visibility": visibility}}
	)
	return res["n"] == 1 and 0 <= res["nModified"] <= 1


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
		{"$sort": {"timestamp": -1}},
		{"$group": {"_id": "$netid", "runs": {"$push": {"_id": "$_id", "timestamp": "$timestamp"}}}},
		{"$sort": {"_id": 1}}
	])


def add_grading_run(cid, aid, netid, timestamp, run_id, extension_used=None):
	"""
	Add a new grading run.
	:param cid: a course ID.
	:param aid: an assignment ID.
	:param netid: a student's NetID.
	:param timestamp: a UNIX timestamp for this run.
	:param run_id: the run ID received from Broadway API. Used to retrieve status.
	:param extension_used: the extension used for this run, if any.
	"""
	new_run = {"_id": run_id, "course_id": cid, "assignment_id": aid, "netid": netid, "timestamp": timestamp}
	if extension_used is not None:
		new_run["extension_used"] = extension_used["_id"]
		extension_used["remaining_runs"] -= 1
		mongo.db.extensions.update({"_id": extension_used["_id"]}, extension_used)
	mongo.db.runs.insert_one(new_run)


def get_grading_run(run_id):
	return mongo.db.runs.find_one({"_id": run_id})


def get_extensions(cid, aid, netid=None):
	if netid is None:
		return mongo.db.extensions.find({"course_id": cid, "assignment_id": aid}).sort("netid", ASCENDING)
	else:
		return mongo.db.extensions.find({"course_id": cid, "assignment_id": aid, "netid": netid})


def add_extension(cid, aid, netid, max_runs, start, end):
	return mongo.db.extensions.insert_one({"course_id": cid, "assignment_id": aid, "netid": netid, "max_runs": max_runs, "remaining_runs": max_runs, "start": start, "end": end})
