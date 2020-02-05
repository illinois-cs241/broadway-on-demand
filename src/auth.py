from functools import wraps
from http import HTTPStatus

from flask import session, redirect, url_for, abort
from src.common import verify_staff, verify_admin


UID_KEY = "netid"
CID_KEY = "cid"


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


def set_uid(uid):
	"""
	Save the current user's NetID with their session.
	:param uid: a NetID.
	"""
	session[UID_KEY] = uid


def logout():
	"""
	Remove the current user's NetID from their session, effectively logging them out. Redirects the user to the login
	page.
	:return: a redirect response to the login page.
	"""
	if UID_KEY in session:
		del session[UID_KEY]
	return redirect(url_for(".login_page"))
