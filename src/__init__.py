from flask import Flask, send_from_directory, render_template, request, redirect
from flask_session import Session

from src import db, bw_api, auth, ghe_api, util, common
from src.config import *
from src.routes_staff import StaffRoutes
from src.routes_student import StudentRoutes
from src.routes_system import SystemRoutes
from src.template_filters import TemplateFilters

app = Flask(__name__)
app.config["SESSION_TYPE"] = SESSION_TYPE
app.config["SESSION_MONGODB_DB"] = SESSION_MONGODB_DB
app.config["MONGO_URI"] = MONGO_URI
db.init(app)
Session(app)


@app.route("/login/", methods=["GET"])
@auth.require_no_auth
def login_page():
	return render_template("login.html")


@app.route("/login/ghe_callback/", methods=["GET"])
def login_ghe_callback():
	code = request.args.get("code")
	if code is None:
		return util.error("Invalid request; missing code argument.")
	access_token = ghe_api.get_access_token(code)
	if access_token is None:
		return redirect("/login/?error=1")
	netid = ghe_api.get_login(access_token)
	if netid is None:
		return redirect("/login/?error=1")
	db.update_user(netid, access_token)
	auth.set_uid(netid)
	return redirect("/")


@app.route("/logout/", methods=["GET"])
@auth.require_auth
def logout(netid):
	return auth.logout()


@app.route("/static/<path>/", methods=["GET"])
def static_file(path):
	return send_from_directory("static", path)


@app.route("/", methods=["GET"])
@auth.require_auth
def root(netid):
	is_student = common.is_student(netid)
	is_staff = common.is_staff(netid)
	if is_student and not is_staff:
		return redirect("/student/")
	if is_staff and not is_student:
		return redirect("/staff/")
	return render_template("home.html", netid=netid)


StudentRoutes(app)
StaffRoutes(app)
TemplateFilters(app)
