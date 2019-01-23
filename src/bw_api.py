import requests

from src.config import BROADWAY_API_TOKEN, BROADWAY_API_URL
from src.util import timestamp_to_bw_api_format

HEADERS = {"Authorization": "Bearer %s" % BROADWAY_API_TOKEN}


def start_grading_run(cid, aid, netid, timestamp):
	"""
	Attempt to start a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param netid: the student's NetID.
	:param timestamp: the UNIX timestamp for the run due date.
	:return: a run_id string if successful, or None otherwise.
	"""
	data = {
		"students_env": [{
			"STUDENT_ID": netid,
			"DUE_DATE": timestamp_to_bw_api_format(timestamp)
		}]
	}
	try:
		resp = requests.post(url="%s/grading_run/%s/%s" % (BROADWAY_API_URL, cid, aid), headers=HEADERS, json=data)
		run_id = resp.json()["data"]["grading_run_id"]
		return run_id
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None


def get_grading_run_status(cid, aid, run_id):
	"""
	Get the status of a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param run_id: the run ID received when the run was started.
	:return: a status string if successful, or None otherwise.
	"""
	try:
		resp = requests.get(url="%s/grading_run/%s/%s/%s" % (BROADWAY_API_URL, cid, aid, run_id), headers=HEADERS)
		return resp.json()["data"]["state"]
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None
