from flask import render_template, abort, request, jsonify
from http import HTTPStatus
import json, re

from src import db, util, auth, bw_api
from src.common import verify_staff, verify_admin, verify_student

class ApiRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/api/<cid>/update_roster", methods=["POST"])
        @auth.require_token_auth
        @auth.require_admin_status
        def admin_update_roster(netid, cid):
            if not verify_staff(netid, cid):
                return abort(HTTPStatus.FORBIDDEN)
            netids = request.form["roster"].split("\n")

            for i, student_id in enumerate(netids):
                if not util.is_valid_netid(student_id):
                    return util.error(f"Poorly formatted NetID on line {i + 1}: '{student_id}'")

            db.overwrite_student_roster(cid, netids)
            return util.success("Successfully updated roster.", 200)

        