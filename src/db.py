from flask_pymongo import PyMongo, ASCENDING, DESCENDING

mongo = PyMongo()


class Quota:
	DAILY = "daily"
	TOTAL = "total"


def init(app):
	mongo.init_app(app)


def get_user(netid):
	return mongo.db.users.find_one({"_id": netid})


def update_user(netid, access_token):
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
	if quota not in [Quota.DAILY, Quota.TOTAL]:
		raise RuntimeError("Invalid quota type for assignment.")
	mongo.db.assignments.insert_one(
		{"course_id": cid, "assignment_id": aid, "max_runs": max_runs, "quota": quota, "start": start, "end": end})


def get_assignment_runs(cid, aid, netid=None):
	if netid:
		return list(
			mongo.db.runs.find({"course_id": cid, "assignment_id": aid, "netid": netid}).sort("timestamp", DESCENDING))
	else:
		return list(
			mongo.db.runs.find({"course_id": cid, "assignment_id": aid}).sort("netid", ASCENDING))


def add_assignment_run(cid, aid, netid, timestamp, run_id):
	mongo.db.runs.insert_one(
		{"_id": run_id, "course_id": cid, "assignment_id": aid, "netid": netid, "timestamp": timestamp})


def get_staff(netid):
	return mongo.db.staff.find_one({"_id": netid})


def get_staff_for_token(token):
	return mongo.db.staff.find_one({"access_token": token})
