from functools import wraps
from http import HTTPStatus

from flask import session, redirect, url_for, abort, request, render_template, make_response
from src.common import verify_staff, verify_admin

import identity.web

from config import SYSTEM_API_TOKEN, MIP_AUTHORITY, MIP_CLIENT_ID, MIP_CLIENT_SECRET, MIP_SCOPES, AUTH_DOMAIN

UID_KEY = "netid"
CID_KEY = "cid"
LOGIN_ERR_KEY = "login_error"

mip_auth = identity.web.Auth(
    session=session,
    authority=MIP_AUTHORITY,
    client_id=MIP_CLIENT_ID,
    client_credential=MIP_CLIENT_SECRET,
)

def get_netid():
	"""
	Gets the logged in user's netid
	"""
	if UID_KEY in session:
		return session[UID_KEY]
	return None


def require_no_auth(func):
	"""
	A route decorator that redirects authenticated users to the site root. If the user is not authenticated, proceeds
	with the route function. Useful for the login page, where users who are already authenticated are not relevant.
	:param func: a route function.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		if UID_KEY in session:
			return redirect(url_for(".root"))
		return func(*args, **kwargs)
	return wrapper


def require_auth(func):
	"""
	A route decorator that redirects unauthenticated users to the login page. If the user is authenticated, proceeds
	with the route function, passing their NetID as the first positional argument.
	:param func: a route function that takes a NetID as its first positional argument.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		if UID_KEY in session:
			kwargs[UID_KEY] = session[UID_KEY]
			return func(*args, **kwargs)
		return redirect(url_for(".login_page"))
	return wrapper


def require_system_auth(func):
        """
        A route decorator to check for the SYSTEM_API_TOKEN in the headers.
        Returns Forbidden if the token is not set
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
                token = request.headers["Authorization"]
                if token != f"Bearer {SYSTEM_API_TOKEN}":
                        return abort(HTTPStatus.FORBIDDEN)
                return func(*args, **kwargs)
        return wrapper

def require_token_auth(func):
	"""
	A route decorator check user's course token for login. 
	This is useful for api calls to this site. A session is not created for such access.
	"""
	@wraps(func)
	def wrapper(*arg, **kwargs):
		token = request.headers["Authorization"]
		cid = kwargs[CID_KEY]
		if cid is None or token is None:
			return abort(HTTPStatus.FORBIDDEN)
		course = db.get_course(cid)
		if course is None or course.get("github_token", None) != token:
			return abort(HTTPStatus.FORBIDDEN)
		return func(*arg, **kwargs)
	return wrapper


def require_admin_status(func):
	"""
	A route decorator that give Forbidden error if the user is not an admin of this
	course.
	:param func: a route function that takes NetID and course id as the first two positional
		arguments.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		netid = kwargs[UID_KEY]
		cid = kwargs[CID_KEY]
		if not verify_staff(netid, cid) or not verify_admin(netid, cid):
			return abort(HTTPStatus.FORBIDDEN)
		return func(*args, **kwargs)
	return wrapper

def begin_login():
	"""
	Render the login page for the user using external IAM service
	"""
	# Have to save error in cookie so error is saved across multiple redirects so user is
	# logged out of Microsoft before coming back to the login page if login fails
	error = request.cookies.get(LOGIN_ERR_KEY, "")

	resp = make_response(render_template("login.html", error=error, success=request.args.get("success", "0"), **mip_auth.log_in(
        scopes=MIP_SCOPES, # Have user consent to scopes during log-in
		redirect_uri=(url_for(".login_callback", _external=True)),
        prompt="login",  # Optional. More values defined in  https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
    )))

	# Reset cookie to empty string
	resp.set_cookie(LOGIN_ERR_KEY, "")

	return resp


def complete_login():
    result = mip_auth.complete_log_in(request.args)
    if "error" in result:
        return render_template("login.html", error=result.get("error_description", ""))

    try:
        email = result["email"]
    except ValueError:
        error = "Could not find email associated with account. Please contact course staff."
        return logout(error)

    if not email.endswith(AUTH_DOMAIN):
        error = f"Account email does not belong to domain \"{AUTH_DOMAIN}\". Please contact course staff."
        return logout(error)

    netid = email[:email.rfind('@')]
    set_uid(netid)
    return redirect(url_for(".root"))


def set_uid(uid):
	"""
	Save the current user's NetID with their session, effectively logging them in.
	:param uid: a NetID.
	"""
	session[UID_KEY] = uid


def logout(error=""):
	"""
	Remove the current user's NetID from their session, effectively logging them out. Redirects the user to the login
	page.
	:param error: any error from previous login attempt
	:return: a redirect response to the login page.
	"""
	if UID_KEY in session:
		del session[UID_KEY]


	success = "1" if error == "" else "0"
	# Use the following to log user out of SSO and Broadway On-Demand
	# resp = make_response(redirect(mip_auth.log_out(url_for(".login_page", success=success, _external=True))))

	mip_auth.log_out("")
	resp = make_response(redirect(url_for(".login_page", success=success)))
	resp.set_cookie(LOGIN_ERR_KEY, error)

	return resp
