from functools import wraps

from flask import session, redirect

UID_KEY = "netid"


def require_no_auth(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if UID_KEY in session:
			return redirect("/")
		return func(*args, **kwargs)
	return wrapper


def require_auth(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if UID_KEY in session:
			return func(session[UID_KEY], *args, **kwargs)
		return redirect("/login/")
	return wrapper


def set_uid(uid):
	session[UID_KEY] = uid


def logout():
	if UID_KEY in session:
		del session[UID_KEY]
	return redirect("/login/")
