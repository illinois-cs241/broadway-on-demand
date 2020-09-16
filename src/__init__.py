from flask import Flask, Blueprint, url_for, send_from_directory, render_template, request, redirect, abort
from flask_session import Session
from werkzeug.urls import url_parse
from http import HTTPStatus

from config import *
from src import db, bw_api, auth, ghe_api, util, common
from src.routes_admin import AdminRoutes
from src.routes_staff import StaffRoutes
from src.routes_api import ApiRoutes
from src.routes_student import StudentRoutes
from src.routes_system import SystemRoutes
from src.template_filters import TemplateFilters
from src.util import generate_csrf_token

app = Flask(__name__)
app.config["SESSION_TYPE"] = SESSION_TYPE
app.config["SESSION_MONGODB_DB"] = SESSION_MONGODB_DB
app.config["MONGO_URI"] = MONGO_URI
app.jinja_env.globals['csrf_token'] = generate_csrf_token
db.init(app)
Session(app)

blueprint = Blueprint('on-demand', __name__, url_prefix=BASE_URL)
StudentRoutes(blueprint)
StaffRoutes(blueprint)
AdminRoutes(blueprint)
ApiRoutes(blueprint)


@blueprint.route("/login/", methods=["GET"])
@auth.require_no_auth
def login_page():
	return render_template("login.html", login_url=GHE_LOGIN_URL)


@blueprint.route("/login/ghe_callback/", methods=["GET"])
def login_ghe_callback():
	code = request.args.get("code")
	if code is None:
		return util.error("Invalid request; missing code argument.")
	access_token = ghe_api.get_access_token(code)
	if access_token is None:
		return redirect(url_for(".login_page") + '?error=1')
	netid = ghe_api.get_login(access_token)
	if netid is None:
		return redirect(url_for(".login_page") + '?error=1')
	db.set_user_access_token(netid, access_token)
	auth.set_uid(netid)
	return redirect(url_for(".root"))


@blueprint.route("/loginas/", methods=["POST"])
def login_as():
	"""
	This function allows developers to be logged in as any user.
	"""
	if app.config['ENV'] != "development":
		return abort(HTTPStatus.FORBIDDEN)
	path = request.args.get("path")
	if not path or url_parse(path).netloc != "":
		path = url_for(".root")
	netid = request.form.get("loginNetId")
	auth.set_uid(netid)
	return redirect(path)


@blueprint.route("/logout/", methods=["GET"])
@auth.require_auth
def logout(netid):
	return auth.logout()


@blueprint.route("/static/<path>", methods=["GET"])
def static_file(path):
	return send_from_directory("static", path)


@blueprint.route("/", methods=["GET"])
@auth.require_auth
def root(netid):
	is_student = common.is_student(netid)
	is_staff = common.is_staff(netid)
	# if a person is not a staff for any course, should skip the "staff" option
	if is_student and not is_staff:
		return redirect(url_for(".student_home"))
	return render_template("home.html", netid=netid)


@app.context_processor
def inject_header_values():
	netid = auth.get_netid()
	is_staff = netid and common.is_staff(netid)

	def switcher_endpoint(course, assignment, mode="student"):
		'''
		This function determines the correct endpoint for the student/staff
		switcher based on the currently selected course/assignment
		'''
		route = "home"
		url_args = {}

		if course:
			# ensure user is staff of current course, 
			# otherwise redirect to staff_home
			if mode == "staff":
				netid = auth.get_netid()
				if not (netid and common.verify_staff(netid, course["_id"])):
					return url_for(f'.{mode}_{route}', **url_args)

			# get urls for current assignment or course
			if assignment:
				route = "get_assignment"
				url_args = {"cid": course["_id"], "aid": assignment["assignment_id"]}
			else:
				route = "get_course"
				url_args = {"cid": course["_id"]}

		return url_for(f'.{mode}_{route}', **url_args)

	return dict(is_staff=is_staff, switcher_endpoint=switcher_endpoint)

app.register_blueprint(blueprint)

TemplateFilters(app)
