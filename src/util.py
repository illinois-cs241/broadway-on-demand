from datetime import datetime
from functools import wraps
from re import fullmatch

from flask import request
from pytz import utc

from src.config import TZ


def check_missing_fields(data, *args):
	"""
	Given a dict and a variable number of keys, returns a list of the keys that are not in the dict or
	that have empty values.
	:param data: a dict or dict-like object.
	:param args: any number of keys, typically strings.
	:return: a list of keys, or [] if all keys existed and had values.
	"""
	missing = []
	for field in args:
		if field not in data:
			missing.append(field)
		elif isinstance(data[field], str) and len(data[field]) == 0:
			missing.append(field)
	return missing


def require_form(fields):
	"""
	A decorator for POST routes that take form-encoded bodies; checks that all fields in the given list of field names
	exist and have non-empty values. If any fields are missing or empty, responds with a descriptive error message. If
	all fields have values, proceeds to the route handler function.
	:param fields: a list of field name strings.
	"""
	def decorator_wrapper(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			missing = check_missing_fields(request.form, *fields)
			missing_str = ", ".join(missing)
			if missing:
				return error("Missing or empty fields: %s." % missing_str)
			return func(*args, **kwargs)
		return wrapper
	return decorator_wrapper


def error(msg, status=400):
	"""
	Builds a response pair with the given error message and status code. The 400 Bad Request status is used if none is
	provided.
	:param msg: A description of the error encountered.
	:param status: An HTTP status code for the response; 400 if not specified.
	"""
	return "%s\n" % msg, status


def valid_id(id_str):
	return bool(fullmatch(r'[a-zA-Z0-9_.\-]+', id_str))


def parse_form_datetime(datetime_local_str):
	return TZ.localize(datetime.strptime(datetime_local_str, "%Y-%m-%dT%H:%M"))


def timestamp_to_iso(timestamp):
	return datetime.utcfromtimestamp(timestamp).isoformat()


def now_timestamp():
	return datetime.utcnow().replace(tzinfo=utc).timestamp()
