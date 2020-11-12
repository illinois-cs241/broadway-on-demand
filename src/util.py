import uuid
import time
from datetime import datetime
from functools import wraps
from re import fullmatch
from http import HTTPStatus

from flask import request, session
from pytz import utc

from config import TZ, MAINTENANCE_MODE, MAINTENANCE_MODE_MESSAGE


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


def disable_in_maintenance_mode(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if MAINTENANCE_MODE:
			return "Broadway on Demand is currently under maintenance.\n{}".format(MAINTENANCE_MODE_MESSAGE), 503
		return func(*args, **kwargs)
	return wrapper


def error(content, status=HTTPStatus.BAD_REQUEST):
	"""
	Builds a response pair with the error content and status code. The Bad Request status is used if none is
	provided.
	:param content: The content of response, could be a string description.
	:param status: An HTTP status code for the response; Bad Request if not specified.
	"""
	return content, status


def success(content, status=HTTPStatus.NO_CONTENT):
	"""
	Builds a response pair with given response content and status code. The No Content (doesn't have to go away from
	current page) status is used if none is provided.
	:param content: The content of response, could be json data or string description
	:param status: An HTTP status code for the response; No Content if not specified
	"""
	return content, status


def generate_csrf_token():
	if '_csrf_token' not in session:
		session['_csrf_token'] = str(uuid.uuid4())
	return session['_csrf_token']


def restore_csrf_token(value):
	session['_csrf_token'] = value


def verify_csrf_token(client_token):
	token = session.pop('_csrf_token', None)
	return token and token == client_token


def valid_id(id_str):
	return bool(fullmatch(r'[a-zA-Z0-9_.\-]+', id_str))


def parse_form_datetime(datetime_local_str):
	try:
		return TZ.localize(datetime.strptime(datetime_local_str, "%Y-%m-%dT%H:%M"))
	except ValueError:
		return None


def timestamp_to_iso(timestamp):
	return datetime.utcfromtimestamp(timestamp).isoformat()


def timestamp_round_up_minute(timestamp):
	if timestamp % 60 == 0:
		return timestamp
	return ((int(timestamp)//60)*60) + 60


def timestamp_to_bw_api_format(timestamp):
	return datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def now_timestamp():
	return datetime.utcnow().replace(tzinfo=utc).timestamp()

def is_valid_netid(netid):
	"""
	Return true if the NetID passed in is a valid NetId
	:param netid: A netid string to be tested
	"""
	return fullmatch(r"[a-zA-Z0-9\-]+", netid) is not None

def test_slow_respond(func):
	"""
	Decorator used to simulate slow server respond. Sleep 5 seconds before processing
	the respond.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		time.sleep(3)
		return func(*args, **kwargs)
	return wrapper