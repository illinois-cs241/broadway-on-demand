import traceback
from types import NoneType
from typing import List
from flask_pymongo import PyMongo, ASCENDING, DESCENDING
from bson.objectid import ObjectId
from bson.errors import InvalidId
from src import util
from src.common import wrap_delete_scheduled_run
from src.sched_api import ScheduledRunStatus
from src.types import StudentInfo

mongo = PyMongo()


class Quota:
    DAILY = "daily"
    TOTAL = "total"

    @classmethod
    def is_valid(cls, quota):
        return quota in [cls.DAILY, cls.TOTAL]


class Visibility:
    HIDDEN = "hidden"
    VISIBLE = "visible"
    VISIBLE_FROM_START = "visible_from_start"


def init(app):
    mongo.init_app(app)


def get_user(netid):
    return mongo.db["users"].find_one({"_id": netid})


def get_courses_for_student_or_staff(netid):
    student_course = get_courses_for_student(netid)
    staff_course = get_courses_for_staff(netid)
    for course in staff_course:
        if course not in student_course:
            student_course.append(course)
    return student_course


def get_courses_for_student(netid: str):
    return list(mongo.db["courses"].find({"student_ids": netid}))


def get_courses_for_staff(netid: str):
    return list(mongo.db["courses"].find({f"staff.{netid}": {"$exists": True}}))


def get_course(cid: str):
    return mongo.db["courses"].find_one({"_id": cid})


def add_staff_to_course(cid: str, new_staff_id: str):
    return mongo.db["courses"].update_one(
        {"_id": cid}, {"$set": {f"staff.{new_staff_id}": {"is_admin": False}}}
    )


def remove_staff_from_course(cid, staff_id):
    return mongo.db["courses"].update_one(
        {"_id": cid}, {"$unset": {f"staff.{staff_id}": 1}}
    )


def add_student_to_course(cid: str, student_info: StudentInfo):
    return mongo.db["courses"].update_one(
        {"_id": cid},
        {
            "$addToSet": {
                "student_ids": student_info["netid"],
                "student_enhanced_mapping": student_info,
            }
        },
    )


def remove_student_from_course(cid: str, student_id: str):
    return mongo.db["courses"].update_one(
        {"_id": cid},
        {
            "$pull": {
                "student_ids": student_id,
                "student_enhanced_mapping": {"netid": student_id},
            }
        },
    )


def add_admin_to_course(cid: str, staff_id: str):
    return mongo.db["courses"].update_one(
        {"_id": cid}, {"$set": {f"staff.{staff_id}.is_admin": True}}
    )


def remove_admin_from_course(cid: str, staff_id: str):
    return mongo.db["courses"].update_one(
        {"_id": cid}, {"$set": {f"staff.{staff_id}.is_admin": False}}
    )


def overwrite_student_roster(cid: str, students: List[StudentInfo]):
    student_ids = list(map(lambda student: student["netid"], students))

    return mongo.db["courses"].update_one(
        {"_id": cid},
        {"$set": {"student_ids": student_ids, "student_enhanced_mapping": students}},
    )


def get_assignments_for_course(cid: str, visible_only: bool = False):
    if not visible_only:
        return list(mongo.db["assignments"].find({"course_id": cid}))

    now = util.now_timestamp()
    query = {
        "course_id": cid,
        "$or": [
            {"visibility": Visibility.VISIBLE_FROM_START, "start": {"$lte": now}},
            {"visibility": Visibility.VISIBLE},
        ],
    }
    return list(mongo.db["assignments"].find(query))


def get_assignment(cid: str, aid: str):
    return mongo.db["assignments"].find_one({"course_id": cid, "assignment_id": aid})


def add_assignment(
    cid: str, aid: str, max_runs: int, quota: str, start: int, end: int, visibility: str
):
    if not Quota.is_valid(quota):
        raise RuntimeError("Invalid quota type for assignment.")

    mongo.db["assignments"].insert_one(
        {
            "course_id": cid,
            "assignment_id": aid,
            "max_runs": max_runs,
            "quota": quota,
            "start": start,
            "end": end,
            "visibility": visibility,
        }
    )


def update_assignment(
    cid: str, aid: str, max_runs: int, quota: str, start: int, end: int, visibility: str
):
    if not Quota.is_valid(quota):
        raise RuntimeError("Invalid quota type for assignment.")

    res = mongo.db["assignments"].update_one(
        {"course_id": cid, "assignment_id": aid},
        {
            "$set": {
                "max_runs": max_runs,
                "quota": quota,
                "start": start,
                "end": end,
                "visibility": visibility,
            }
        },
    )
    return res.modified_count == 1


def remove_assignment(cid: str, aid: str):
    delete_filter = {"course_id": cid, "assignment_id": aid}
    mongo.db["extensions"].delete_many(delete_filter)
    mongo.db["runs"].delete_many(delete_filter)
    res = mongo.db["assignments"].delete_many(delete_filter)
    # delete scheduled runs for this assignment
    mongo.db["scheduled_runs"].delete_many(delete_filter)
    return res.deleted_count == 1


def get_assignment_runs_for_student(cid: str, aid: str, netid: str):
    return list(
        mongo.db["runs"]
        .find({"course_id": cid, "assignment_id": aid, "netid": netid})
        .sort("timestamp", DESCENDING)
    )


def get_assignment_runs(cid: str, aid: str):
    return mongo.db["runs"].aggregate(
        [
            {"$match": {"course_id": cid, "assignment_id": aid}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$netid",
                    "runs": {"$push": {"_id": "$_id", "timestamp": "$timestamp"}},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    )


def get_scheduled_runs(cid: str, aid: str):
    return (
        mongo.db["scheduled_runs"]
        .find({"course_id": cid, "assignment_id": aid})
        .sort("run_time", DESCENDING)
    )


def add_grading_run(
    cid: str,
    aid: str,
    netid: str,
    timestamp: float,
    run_id: str,
    extension_used: str | NoneType = None,
):
    new_run = {
        "_id": run_id,
        "course_id": cid,
        "assignment_id": aid,
        "netid": netid,
        "timestamp": timestamp,
    }

    if extension_used:
        mongo.db["extensions"].update_one(
            {"_id": extension_used["_id"]},
            {"$set": {"_id": extension_used["_id"]}, "$inc": {"remaining_runs": -1}}
        )

    mongo.db["runs"].insert_one(new_run)

def remove_grading_run(cid, aid, netid, run_id, extension_used: str | NoneType = None):
    run = {
        "_id": run_id,
        "course_id": cid,
        "assignment_id": aid,
        "netid": netid,
    }
    result = mongo.db["runs"].delete_one(run)
    if result.deleted_count != 1:
        return

    if extension_used:
        mongo.db["extensions"].update_one(
            {"_id": extension_used["_id"]},
            {"$set": {"_id": extension_used["_id"]}, "$inc": {"remaining_runs": 1}}
        )

def get_grading_run(run_id: str):
    return mongo.db["runs"].find_one({"_id": run_id})


def get_extensions(cid: str, aid: str, netid: str | NoneType = None):
    query = {"course_id": cid, "assignment_id": aid, "remaining_runs": {"$gt": 0}} # avoid making one of them negative
    if netid:
        query["netid"] = netid
    return mongo.db["extensions"].find(query).sort("netid", ASCENDING).sort("remaining_runs", ASCENDING)


def pair_assignment_final_grading_run(cid: str, aid: str, scheduled_run_id: ObjectId):
    return mongo.db["assignments"].update_one(
        {"course_id": cid, "assignment_id": aid},
        {"$set": {"final_grading_run_id": str(scheduled_run_id)}},
    )


def add_extension(
    cid, aid, netid, max_runs, start, end, scheduled_run_id: ObjectId = None, userRequested: bool = False
):
    return mongo.db["extensions"].insert_one(
        {
            "course_id": cid,
            "assignment_id": aid,
            "netid": netid,
            "max_runs": max_runs,
            "remaining_runs": max_runs,
            "start": start,
            "end": end,
            "run_id": str(scheduled_run_id) if scheduled_run_id else None,
            "userRequested": userRequested
        }
    )


def delete_extension(cid: str, aid: str, extension_id: str):
    try:
        document = mongo.db["extensions"].find_one({"_id": ObjectId(extension_id)})
        if not document:
            return None

        if run_id := document.get("run_id"):
            try:
                wrap_delete_scheduled_run(cid, aid, run_id)
            except Exception as e:
                print(
                    f"Failed to delete scheduled run for extension id {extension_id} run id {run_id}: {e}",
                    flush=True,
                )

        return mongo.db["extensions"].delete_one({"_id": ObjectId(extension_id)})
    except InvalidId:
        return None


def add_or_update_scheduled_run(
    rid,
    cid,
    aid,
    run_time,
    due_time,
    roster,
    name,
    scheduled_run_id,
    bw_run_id=None,
    status=ScheduledRunStatus.SCHEDULED,
):
    sched_run_obj = {
        "course_id": cid,
        "assignment_id": aid,
        "run_time": run_time,
        "due_time": due_time,
        "roster": roster,
        "name": name,
        "scheduled_run_id": scheduled_run_id,
        "broadway_run_id": bw_run_id,
        "status": status,
    }

    res = mongo.db["scheduled_runs"].update_one(
        {"_id": ObjectId(rid)}, {"$set": sched_run_obj}, upsert=True
    )
    return res.upserted_id is not None or res.matched_count > 0


def update_scheduled_run_status(rid, status):
    res = mongo.db["scheduled_runs"].update_one(
        {"_id": ObjectId(rid)}, {"$set": {"status": status}}
    )
    return res.modified_count > 0


def update_scheduled_run_bw_run_id(rid, bw_run_id):
    res = mongo.db["scheduled_runs"].update_one(
        {"_id": ObjectId(rid)}, {"$set": {"broadway_run_id": bw_run_id}}
    )
    return res.modified_count > 0


def get_scheduled_run(cid, aid, rid):
    try:
        return mongo.db["scheduled_runs"].find_one(
            {"_id": ObjectId(rid), "course_id": cid, "assignment_id": aid}
        )
    except InvalidId:
        return None


def get_scheduled_run_by_scheduler_id(cid, aid, scheduled_run_id):
    return list(mongo.db["scheduled_runs"].find(
        {"scheduled_run_id": scheduled_run_id, "course_id": cid, "assignment_id": aid}
    ))


def delete_scheduled_run(cid, aid, rid):
    try:
        res = mongo.db["scheduled_runs"].delete_one(
            {"_id": ObjectId(rid), "course_id": cid, "assignment_id": aid}
        )
        return res.deleted_count == 1
    except InvalidId:
        return False


def set_jenkins_run_status(cid, rid, status, build_url, netid):
    mongo.db["jenkins_run_status"].update_one(
        {"cid": cid, "rid": rid, "netid": netid},
        {"$set": {"status": status, "build_url": build_url}},
        upsert=True,
    )


def get_jenkins_run_status_single(cid, rid, netid):
    try:
        query = {"cid": cid, "rid": rid, "netid": netid}
        if not netid:
            query = {"cid": cid, "rid": rid}
        response = mongo.db["jenkins_run_status"].find_one(
            query, {"_id": 0}
        )
        return response or {}
    except Exception as e:
        print(e, flush=True)
        return {}


def get_jenkins_run_status_all(cid, rid):
    try:
        response = mongo.db["jenkins_run_status"].find(
            {"cid": cid, "rid": rid}, {"_id": 0, "netid": 1, "status": 1}
        )
        return list(response) if response else []
    except Exception as e:
        print(e, flush=True)
        return []

def get_course_grades(cid):
    try:
        response = mongo.db["new_gv_assignments"].find(
            {"courseId": cid}, {"_id": 0, "__v": 0, "courseId": 0}
        ).sort({"dueDate": -1})
        return list(response)
    except Exception as e:
        print(e, flush=True)
        return []
    
def get_user_requested_extensions(cid, netid):
    try:
        response = mongo.db["extensions"].find(
            {"course_id": cid, "netid": netid, "userRequested": True}, {"_id": 0, "__v": 0, "courseId": 0}
        ).sort({"dueDate": -1})
        course_data = mongo.db["courses"].find_one({"_id": cid}, {"_id": 0, "num_student_extensions": 1, "num_ext_hours": 1, "last_assignment_due_date": 1})
        allowed_extensions = 0
        num_ext_hours = 0
        last_assignment_due_date = 0
        if 'num_student_extensions' in course_data:
            allowed_extensions = course_data['num_student_extensions']
        if 'num_ext_hours' in course_data:
            num_ext_hours = course_data['num_ext_hours']
        if 'last_assignment_due_date' in course_data:
            last_assignment_due_date = course_data['last_assignment_due_date']
        robj = {"existing_extensions": list(response), "total_allowed": allowed_extensions, "num_hours": num_ext_hours, "last_assignment_due_date": last_assignment_due_date}
        return robj
    except Exception as e:
        print(traceback.format_exc(), flush=True)
        return []

def find_referenced_scheduled_runs(scheduled_run_id: str) -> int:
    """Find the number of scheduled runs which use a given scheduled run id"""
    return mongo.db['scheduled_runs'].count_documents({"scheduled_run_id": scheduled_run_id})