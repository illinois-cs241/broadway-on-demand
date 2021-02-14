from subprocess import check_output, CalledProcessError
from http import HTTPStatus
import logging
from flask import render_template, abort, jsonify

from config import TZ
from src import db, util, auth, bw_api, sched_api
from src.common import verify_staff, verify_admin

import pathlib
import subprocess

logger = logging.getLogger(__name__)


class StaffRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/staff/", methods=["GET"])
        @auth.require_auth
        def staff_home(netid):
            courses = db.get_courses_for_staff(netid)
            version_code = 'unknown'
            try:

                '''
                    Below is a fix, to get the git versionCode displayed on the front end
                    The workaround is to get the absolute path to the current directory, then cd into that folder, then run your git command.
                    We need to do this, because many times we will start the service from outside the current directory.

                    The code below will only work in a linux like environment. It requires the exeuctable env and git to be in /usr/bin.
                    If git is not in that location, then you can modify the parameters to the subproccess.Popen call as necessary.              
                '''

                curDirPath = str(pathlib.Path(__file__).parent.absolute())
                git_hash = subprocess.Popen(['/usr/bin/env', 'PATH=/usr/bin/', 'git', 'rev-parse', '--short=8', 'HEAD'], stdout=subprocess.PIPE, cwd=curDirPath).communicate()[0].strip().decode()
                    
                if len(git_hash) >= 8:
                    version_code = git_hash[0:8]

            except CalledProcessError as e:
                logger.error(f"Failed to get git hash; return code: {e.returncode}, command ran: {e.cmd}, output of "
                             f"process: {e.output}")

            return render_template("staff/home.html", netid=netid, courses=courses, version_code=version_code)

        @blueprint.route("/staff/course/<cid>/", methods=["GET"])
        @auth.require_auth
        def staff_get_course(netid, cid):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            course = db.get_course(cid)
            assignments = db.get_assignments_for_course(cid)
            is_admin = verify_admin(netid, cid)
            now = util.now_timestamp()
            return render_template("staff/course.html", netid=netid, course=course, assignments=assignments,
                                   tzname=str(TZ), is_admin=is_admin, now=now, visibility=db.Visibility, error=None)

        @blueprint.route("/staff/course/<cid>/<aid>/", methods=["GET"])
        @auth.require_auth
        def staff_get_assignment(netid, cid, aid):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            course = db.get_course(cid)
            assignment = db.get_assignment(cid, aid)
            student_runs = list(db.get_assignment_runs(cid, aid))
            scheduled_runs = list(db.get_scheduled_runs(cid, aid))
            is_admin = verify_admin(netid, cid)

            return render_template("staff/assignment.html", netid=netid, course=course,
                                   assignment=assignment, student_runs=student_runs,
                                   scheduled_runs=scheduled_runs, sched_run_status=sched_api.ScheduledRunStatus,
                                   tzname=str(TZ), is_admin=is_admin, visibility=db.Visibility)

        @blueprint.route("/staff/course/<cid>/<aid>/config", methods=["GET"])
        @auth.require_auth
        def staff_get_assignment_config(netid, cid, aid):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            config = bw_api.get_assignment_config(cid, aid)

            if config is None:
                return abort(404)

            return jsonify(config)

        @blueprint.route("/staff/course/<cid>/<aid>/<run_id>/status/", methods=["GET"])
        @auth.require_auth
        def staff_get_job_status(netid, cid, aid, run_id):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            status = bw_api.get_grading_job_status(cid, run_id)
            if status:
                return util.success(status, HTTPStatus.OK)
            return util.error("")

        @blueprint.route("/staff/course/<cid>/<aid>/<run_id>/state/", methods=["GET"])
        @auth.require_auth
        def staff_get_run_state(netid, cid, aid, run_id):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            state = bw_api.get_grading_run_state(cid, run_id)
            if state:
                return util.success(state, HTTPStatus.OK)
            return util.error("")

        @blueprint.route("/staff/course/<cid>/<aid>/<run_id>/log/", methods=["GET"])
        @auth.require_auth
        def staff_get_run_log(netid, cid, aid, run_id):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            log = bw_api.get_grading_run_log(cid, run_id)
            if log:
                return util.success(jsonify(log), HTTPStatus.OK)
            return util.error("")

        @blueprint.route("/staff/course/<cid>/workers/", methods=["GET"])
        @auth.require_auth
        def staff_get_workers(netid, cid):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)

            workers = bw_api.get_workers(cid)
            if workers:
                return util.success(jsonify(workers), HTTPStatus.OK)
            return util.error("")
