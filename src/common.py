from datetime import datetime

from pytz import utc

from src import db, util
from src.config import TZ


def in_grading_period(assignment, now=None):
	if now is None:
		now = util.now_timestamp()
	return assignment["start"] <= now <= assignment["end"]


def is_run_today(run, now):
	today = datetime.utcfromtimestamp(now).replace(tzinfo=utc).astimezone(TZ).date()
	run_date = datetime.utcfromtimestamp(run["timestamp"]).replace(tzinfo=utc).astimezone(TZ).date()
	return run_date == today


def get_remaining_runs(assignment, runs, now=None):
	if now is None:
		now = util.now_timestamp()
	if assignment["quota"] == db.Quota.TOTAL:
		return assignment["max_runs"] - len(runs)
	elif assignment["quota"] == db.Quota.DAILY:
		today_runs = list(filter(lambda r: is_run_today(r, now), runs))
		return assignment["max_runs"] - len(today_runs)


def is_student(netid):
	""""""
	courses = db.get_courses_for_student(netid)
	return bool(courses)


def is_staff(netid):
	"""
	Check whether the given NetID is a staff member of at least 1 course.
	:param netid: a user's NetID.
	:return: a boolean value.
	"""
	courses = db.get_courses_for_staff(netid)
	return bool(courses)


def verify_student(netid, cid):
	"""
	Check whether the given NetID is a student in the given course.
	:param netid: a user's NetID.
	:param cid: a course ID.
	:return: a boolean value.
	"""
	return netid in db.get_course(cid)["student_ids"]


def verify_admin(netid, cid):
	"""
	Check whether the given NetID is a course admin in the given course.
	:param netid: a user's NetID.
	:param cid: a course ID.
	:return: a boolean value.
	"""
	return netid in db.get_course(cid)["admin_ids"]


def verify_staff(netid, cid):
	"""
	Check whether the given NetID is a staff member in the given course.
	:param netid: a user's NetID.
	:param cid: a course ID.
	:return: a boolean value.
	"""
	return netid in db.get_course(cid)["staff_ids"]


def verify_cid(cid):
	return db.get_course(cid) is not None


def verify_aid(cid, aid):
	return db.get_assignment(cid, aid) is not None
