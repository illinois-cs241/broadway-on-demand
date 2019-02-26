from functools import wraps

from flask import session, redirect, url_for

UID_KEY = "netid"


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
			return func(session[UID_KEY], *args, **kwargs)
		return redirect(url_for(".login_page"))
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
