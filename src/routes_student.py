from datetime import datetime, timedelta
import json
import traceback
from typing import List
from bson import ObjectId
from flask import render_template, request, abort
from http import HTTPStatus
import math

from config import BASE_URL, TZ, DEV_MODE
from src import auth, jenkins_api, util, db
from src.common import (
    verify_student_or_staff,
    verify_staff,
    get_available_runs,
    get_active_extensions,
)
from src.ghe_api import get_latest_commit
from src.types import GradeEntry
from src.util import bin_scores, compute_statistics, verify_csrf_token, restore_csrf_token
from src.routes_admin import add_or_edit_scheduled_run
from uuid import uuid4

NO_EXTENSION_ASSIGNMENTS = set(['malloc_contest', 'lovable_linux'])

def compute_extension_parameters(assignment, extension_info):
    num_periods = 0
    num_runs_per_period = 0
    if assignment['quota'] == db.Quota.DAILY:
        num_periods = extension_info['num_hours'] // 24
        num_runs_per_period = assignment['max_runs']
    elif assignment['quota'] == db.Quota.TOTAL:
        num_periods = 1
        num_runs_per_period = math.ceil(((extension_info['num_hours'] / ((assignment['end'] - assignment['start']) / 3600))) * assignment['max_runs'])
    return num_periods, num_runs_per_period

class StudentRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/student/", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_home(netid):
            # staff should be able to see course as a student
            courses = db.get_courses_for_student_or_staff(netid)
            return render_template("student/home.html", netid=netid, courses=courses)

        @blueprint.route("/student/course/<cid>/", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_get_course(netid, cid):
            course = db.get_course(cid)
            if course is None:
                return abort(HTTPStatus.NOT_FOUND)
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            if verify_staff(netid, cid):
                assignments = db.get_assignments_for_course(cid)
            else:
                assignments = db.get_assignments_for_course(cid, visible_only=True)

            now = util.now_timestamp()

            for assignment in assignments:
                num_available_runs = get_available_runs(
                    cid, assignment["assignment_id"], netid, now
                )
                active_extensions, num_extension_runs = get_active_extensions(
                    cid, assignment["assignment_id"], netid, now
                )
                total_available_runs = num_extension_runs + num_available_runs

                if verify_staff(netid, cid):
                    total_available_runs = max(total_available_runs, 1)

                assignment.update({"total_available_runs": total_available_runs})

            return render_template(
                "student/course.html",
                netid=netid,
                course=course,
                assignments=assignments,
                now=now,
                tzname=str(TZ),
            )

        @blueprint.route("/student/course/<cid>/grades/", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_grades(netid, cid):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            course = db.get_course(cid)
            all_grades = db.get_course_grades(cid)
            grades_parsed: List[GradeEntry] = []
            for assignment in all_grades:
                assignment_grades = []
                for student in assignment['data']:
                    assignment_grades.append(float(student['score']))
                real_name = assignment['name'].replace("_", " ").title()
                result = compute_statistics(real_name, assignment['type'], assignment_grades)
                result['bins'] = bin_scores(assignment_grades)
                try:
                    filtered = [float(x['score']) for x in assignment['data'] if x['netid'] == netid]
                    result['score'] = round(filtered[0], 3)
                except Exception:
                    result['score'] = 0
                grades_parsed.append(result)
  
            return render_template("student/grades.html", netid=netid, course=course, grades=json.dumps(grades_parsed))

        @blueprint.route("/student/course/<cid>/extensions/", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_request_extension(netid, cid):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)
            course = db.get_course(cid)
            extension_info = db.get_user_requested_extensions(cid, netid)
            already_extended = set([x['assignment_id'] for x in extension_info['existing_extensions']])
            # filter valid assignments
            # malloc specific escape hatch and check that assignment is open currently
            now = util.now_timestamp()
            raw_assignments =  db.get_assignments_for_course(cid, visible_only=True)
            raw_assignments = list(filter(lambda x: x['end'] >= now, raw_assignments))
            assignments = list(filter(lambda x: x['assignment_id'] not in NO_EXTENSION_ASSIGNMENTS and x['assignment_id'] not in already_extended, raw_assignments))
            # don't enable extending assignments that are already due past reading day (used for regrades portion of the class)
            assignments = list(filter(lambda x: x['end'] < course['last_assignment_due_date'], assignments))
            for assignment in assignments:
                assignment['extended_to'] = assignment['end'] + extension_info['num_hours'] * 3600
                if extension_info['last_assignment_due_date'] != 0:
                   assignment['extended_to'] = min(assignment['extended_to'], extension_info['last_assignment_due_date'])
            return render_template("student/request_extension.html",
                base_url=BASE_URL,
                netid=netid,
                course=course,
                extension_info=extension_info,
                assignments=assignments,
                granted=None,
                tzname=str(TZ),
                )

        @blueprint.route("/student/course/<cid>/extensions/", methods=["POST"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_request_extension_post(netid, cid):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)
            if not verify_csrf_token(request.form.get("csrf_token")):
                return abort(HTTPStatus.BAD_REQUEST)
            current_csrf_token = request.form.get("csrf_token")
            assignment_id = request.form.get("assignment")
            course = db.get_course(cid)
            extension_info = db.get_user_requested_extensions(cid, netid)
            already_extended = set([x['assignment_id'] for x in extension_info['existing_extensions']])
            # filter valid assignments
            # malloc specific escape hatch and check that assignment is open currently
            now = util.now_timestamp()
            raw_assignments =  db.get_assignments_for_course(cid, visible_only=True)
            raw_assignments = list(filter(lambda x: x['end'] >= now, raw_assignments))
            assignments = list(filter(lambda x: x['assignment_id'] not in NO_EXTENSION_ASSIGNMENTS and x['assignment_id'] not in already_extended, raw_assignments))
            for assignment in assignments:
                assignment['extended_to'] = assignment['end'] + extension_info['num_hours'] * 3600
                if extension_info['last_assignment_due_date'] != 0:
                   assignment['extended_to'] = min(assignment['extended_to'], extension_info['last_assignment_due_date'])
            invalid = False
            # cannot grant more extensions than are available
            invalid = invalid or (len(extension_info['existing_extensions']) > extension_info['total_allowed'])
            # can't extend an already extended assignment
            invalid = invalid or (assignment_id in already_extended)
            if invalid:
                restore_csrf_token(current_csrf_token)
                return render_template("student/request_extension.html",
                    base_url=BASE_URL,
                    netid=netid,
                    course=course,
                    extension_info=extension_info,
                    assignments=assignments,
                    granted=False,
                    tzname=str(TZ),
                )
            # the request is valid, actually grant the extension
            # first, figure out how many additional runs for the number of hours that will be granted 
            granted = False
            try:
                assignment = db.get_assignment(cid, assignment_id)
                ext_start_raw = assignment['end'] + 1
                ext_end_raw = assignment['end'] + extension_info['num_hours'] * 3600
                if extension_info['last_assignment_due_date'] != 0:
                    ext_end_raw = min(ext_end_raw, extension_info['last_assignment_due_date'])
                num_periods, num_runs_per_period = compute_extension_parameters(assignment, extension_info)
                sched_run_duedate = datetime.fromtimestamp(ext_end_raw)
                # avoid that weird race condition - start run 5 min after, but with a container due date of the original time
                schedrun_start_time = sched_run_duedate + timedelta(minutes=5)
                run_id = ObjectId()
                response = add_or_edit_scheduled_run(
                    cid,
                    assignment_id,
                    run_id,
                    {
                        "run_time": schedrun_start_time.strftime("%Y-%m-%dT%H:%M"),
                        "due_time": sched_run_duedate.strftime("%Y-%m-%dT%H:%M"),
                        "name": f"Extension Run - {netid}",
                        "roster": netid,
                    },
                    None,
                )
                if response[1] != HTTPStatus.NO_CONTENT:
                    raise Exception(f"Failed to schedule student-requested extension run: {response[0]}")
                db.add_extension(
                    cid,
                    assignment_id,
                    netid,
                    num_periods * num_runs_per_period, 
                    ext_start_raw,
                    ext_end_raw,
                    scheduled_run_id=run_id,
                    userRequested=True,
                )
                # malloc escape hatch - grant extensions for malloc_contest with any malloc assignment
                if assignment_id.startswith("malloc_"):
                    assignment_contest = db.get_assignment(cid, "malloc_contest")
                    num_periods_contest, num_runs_per_period_contest = compute_extension_parameters(assignment_contest, extension_info)
                    # avoid that weird race condition - start run 5 min after, but with a container due date of the original time
                    run_id = ObjectId()
                    add_or_edit_scheduled_run(
                        cid,
                        "malloc_contest",
                        run_id,
                        {
                            "run_time": schedrun_start_time.strftime("%Y-%m-%dT%H:%M"),
                            "due_time": sched_run_duedate.strftime("%Y-%m-%dT%H:%M"),
                            "name": f"Extension Run - {netid}",
                            "roster": netid,
                        },
                        None,
                    )
                    db.add_extension(
                        cid,
                        "malloc_contest",
                        netid,
                        num_periods_contest * num_runs_per_period_contest, 
                        ext_start_raw,
                        ext_end_raw,
                        scheduled_run_id=run_id,
                        userRequested=False
                    )
                granted = True
            except Exception:
                print(traceback.format_exc(), flush=True)
                granted = False

            return render_template("student/request_extension.html",
                base_url=BASE_URL,
                netid=netid,
                course=course,
                extension_info=db.get_user_requested_extensions(cid, netid) if granted else extension_info,
                assignments=assignments,
                granted=granted,
                tzname=str(TZ),
            )

        @blueprint.route("/student/course/<cid>/assignment/<aid>/", methods=["GET"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_get_assignment(netid, cid, aid):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            course = db.get_course(cid)
            assignment = db.get_assignment(cid, aid)
            runs = db.get_assignment_runs_for_student(cid, aid, netid)
            now = util.now_timestamp()

            num_available_runs = get_available_runs(cid, aid, netid, now)
            active_extensions, num_extension_runs = get_active_extensions(
                cid, aid, netid, now
            )

            user = db.get_user(netid)
            token = course.get("github_token", "")
            commit = {
                "message": "This is a test commit.",
                "sha": "2db06991c7846ade1b505e80fbaf257e034c4bd5",
                "url": "https://github.com/illinois-cs241/broadway-on-demand",
            }
            if not DEV_MODE:
                commit = get_latest_commit(
                    netid, token, course["github_org"], course["github_repo_prefix"]
                )
            feedback_url = (
                f'https://github.com/{course["github_org"]}/{course["github_repo_prefix"]}_{netid}/tree/{course["feedback_branch_name"]}'
                if "feedback_branch_name" in course
                else None
            )
            if verify_staff(netid, cid):
                num_available_runs = max(num_available_runs, 1)

            return render_template(
                "student/assignment.html",
                base_url=BASE_URL,
                netid=netid,
                course=course,
                assignment=assignment,
                commit=commit,
                runs=runs,
                num_available_runs=num_available_runs,
                num_extension_runs=num_extension_runs,
                tzname=str(TZ),
                feedback_url=feedback_url,
            )

        @blueprint.route("/student/course/<cid>/assignment/<aid>/run/", methods=["POST"])
        @util.disable_in_maintenance_mode
        @auth.require_auth
        def student_grade_assignment(netid, cid, aid):
            if not verify_student_or_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)
            if not verify_csrf_token(request.form.get("csrf_token")):
                return abort(HTTPStatus.BAD_REQUEST)

            now = util.now_timestamp()
            ext_to_use = None
            current_csrf_token = request.form.get("csrf_token")

            if not verify_staff(netid, cid):
                # not a staff member; perform quota checks
                num_available_runs = get_available_runs(cid, aid, netid, now)
                active_extensions, num_extension_runs = get_active_extensions(
                    cid, aid, netid, now
                )
                if num_available_runs + num_extension_runs <= 0:
                    restore_csrf_token(current_csrf_token)
                    return util.error("No grading runs available.")
                if num_available_runs <= 0:
                    # find the extension that is closest to expiration
                    ext_to_use = min(active_extensions, key=lambda ext: ext["end"])

            now_rounded = util.timestamp_round_up_minute(now)
            run_id = str(uuid4())
            db.add_grading_run(cid, aid, netid, now, run_id, extension_used=ext_to_use)
            run_status = jenkins_api.start_grading_run(
                cid, aid, [netid], now_rounded, False, grading_run_id=run_id
            )
            if run_status is None:
                restore_csrf_token(current_csrf_token)
                db.remove_grading_run(cid, aid, netid, run_id, extension_used=ext_to_use)
                return util.error("Failed to start grading run. Please try again.")
            db.set_jenkins_run_status(
                cid, run_id, "scheduled", None, netid
            )  # null refers to the overall job, which for one-user jobs is what we want.

            return util.success("")
