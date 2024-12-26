from datetime import datetime

from pytz import utc

from config import TZ
from src import db, sched_api, util


def wrap_delete_scheduled_run(cid, aid, run_id):
    sched_run = db.get_scheduled_run(cid, aid, run_id)
    if sched_run is None:
        raise Exception("Cannot find scheduled run")
    sched_api.delete_scheduled_run(sched_run["scheduled_run_id"])
    if not db.delete_scheduled_run(cid, aid, run_id):
        raise Exception("Failed to delete scheduled run.")
    return True


def in_grading_period(assignment, now=None):
    if now is None:
        now = util.now_timestamp()
    return assignment["start"] <= now <= assignment["end"]


def is_run_today(run, now):
    today = datetime.utcfromtimestamp(now).replace(tzinfo=utc).astimezone(TZ).date()
    run_date = (
        datetime.utcfromtimestamp(run["timestamp"])
        .replace(tzinfo=utc)
        .astimezone(TZ)
        .date()
    )
    return run_date == today


def get_available_runs(cid, aid, netid, now=None):
    if now is None:
        now = util.now_timestamp()

    assignment = db.get_assignment(cid, aid)

    if not in_grading_period(assignment, now):
        return 0

    runs = db.get_assignment_runs_for_student(cid, aid, netid)

    if assignment["quota"] == db.Quota.TOTAL:
        return max(assignment["max_runs"] - len(runs), 0)
    elif assignment["quota"] == db.Quota.DAILY:
        today_runs = list(filter(lambda r: is_run_today(r, now), runs))
        return max(assignment["max_runs"] - len(today_runs), 0)


def get_active_extensions(cid, aid, netid, now=None):
    if now is None:
        now = util.now_timestamp()
    extensions = db.get_extensions(cid, aid, netid)
    active_extensions = list(
        filter(lambda ext: ext["start"] <= now <= ext["end"], extensions)
    )
    num_extension_runs = sum(map(lambda ext: ext["remaining_runs"], active_extensions))
    return active_extensions, num_extension_runs


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
    try:
        return netid in db.get_course(cid)["student_ids"]
    except Exception:
        return []


def verify_student_or_staff(netid, cid):
    """
    Check whether the given NetID is a student or a staff in the given course.
    :param netid: a user's NetID.
    :param cid: a course ID.
    :return: a boolean value.
    """
    return verify_student(netid, cid) or verify_staff(netid, cid)


def verify_admin(netid, cid):
    """
    Check whether the given NetID is a course admin in the given course.
    :param netid: a user's NetID.
    :param cid: a course ID.
    :return: a boolean value.
    """
    course = db.get_course(cid)
    return (
        course is not None
        and netid in course["staff"]
        and course["staff"][netid]["is_admin"]
    )


def verify_staff(netid, cid):
    """
    Check whether the given NetID is a staff member in the given course.
    :param netid: a user's NetID.
    :param cid: a course ID.
    :return: a boolean value.
    """
    course = db.get_course(cid)
    return course is not None and netid in course["staff"]
