import json
from typing import List
from flask import render_template, request, abort
from http import HTTPStatus

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

            run_id = jenkins_api.start_grading_run(
                cid, aid, [netid], now_rounded, False
            )
            db.set_jenkins_run_status(
                cid, run_id, "scheduled", None, netid
            )  # null refers to the overall job, which for one-user jobs is what we want.
            if run_id is None:
                restore_csrf_token(current_csrf_token)
                return util.error("Failed to start grading run. Please try again.")

            db.add_grading_run(cid, aid, netid, now, run_id, extension_used=ext_to_use)
            return util.success("")
