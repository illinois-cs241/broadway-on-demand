from flask import request
from http import HTTPStatus

from src import db, util, auth

class ApiRoutes:
    def __init__(self, blueprint):
        @blueprint.route("/api/<cid>/update_roster", methods=["POST"])
        @auth.require_token_auth
        @auth.require_admin_status
        def admin_update_roster(netid, cid):
            netids = request.form["roster"].split("\n")

            for i, student_id in enumerate(netids):
                if not util.is_valid_netid(student_id):
                    return util.error(f"Poorly formatted NetID on line {i + 1}: '{student_id}'")

            db.overwrite_student_roster(cid, netids)
            return util.success("Successfully updated roster.", HTTPStatus.OK)

        