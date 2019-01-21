from datetime import datetime

from src import db
from src.config import TZ


def in_grading_period(assignment, now=None):
	if now is None:
		now = datetime.utcnow().timestamp()
	return assignment["start"] <= now <= assignment["end"]


def is_run_today(run, now):
	today = TZ.localize(datetime.utcfromtimestamp(now)).date()
	run_date = TZ.localize(datetime.utcfromtimestamp(run["timestamp"])).date()
	return run_date == today


def get_remaining_runs(assignment, runs, now=None):
	if now is None:
		now = datetime.utcnow().timestamp()
	if assignment["quota"] == db.Quota.TOTAL:
		return assignment["max_runs"] - len(runs)
	elif assignment["quota"] == db.Quota.DAILY:
		today_runs = list(filter(lambda r: is_run_today(r, now), runs))
		return assignment["max_runs"] - len(today_runs)


def is_student(netid):
	courses = db.get_courses_for_student(netid)
	return bool(courses)


def is_staff(netid):
	courses = db.get_courses_for_staff(netid)
	return bool(courses)