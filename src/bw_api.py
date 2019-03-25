import logging
from json.decoder import JSONDecodeError

import requests

from config import BROADWAY_API_TOKEN, BROADWAY_API_URL
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
	except requests.exceptions.RequestException as e:
		logging.error("start_grading_run(cid={}, aid={}, netid={}): {}".format(cid, aid, netid, repr(e)))
		return None
	except KeyError as e:
		logging.error("start_grading_run(cid={}, aid={}, netid={}): {}".format(cid, aid, netid, repr(e)))
		return None
	except JSONDecodeError as e:
		logging.error("start_grading_run(cid={}, aid={}, netid={}): {}".format(cid, aid, netid, repr(e)))
		return None


def get_grading_run_status(cid, run_id):
	"""
	Get the status of a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param run_id: the run ID received when the run was started.
	:return: a status string if successful, or None otherwise.
	"""
	try:
		resp = requests.get(url="%s/grading_run_status/%s/%s" % (BROADWAY_API_URL, cid, run_id), headers=HEADERS)
		student_jobs_dict = resp.json()["data"]["student_jobs_state"]
		return list(student_jobs_dict.values())[0]
	except requests.exceptions.RequestException as e:
		logging.error("get_grading_run_status(cid={}, run_id={}): {}".format(cid, run_id, repr(e)))
		return None
	except KeyError as e:
		logging.error("get_grading_run_status(cid={}, run_id={}): {}".format(cid, run_id, repr(e)))
		return None
	except JSONDecodeError as e:
		logging.error("get_grading_run_status(cid={}, run_id={}): {}".format(cid, run_id, repr(e)))
		return None


def get_assignment_config(cid, aid):
	"""
	Get run config for an assignment
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	"""

	try:
		resp = requests.get(url="%s/grading_config/%s/%s" % (BROADWAY_API_URL, cid, aid), headers=HEADERS)

		if resp.status_code == 200:
			ret_data = resp.json()
			return ret_data["data"]
	except Exception as e:
		logging.error("get_assignment_config(cid={}, aid={}): {}".format(cid, aid, repr(e)))

	return None


def set_assignment_config(cid, aid, config):
	"""
	Set run config for an assignment. Return error message if failed
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param config: assignemnt config(pre-processing pipeline, student pipelines, etc.)
	"""

	try:
		resp = requests.post(url="%s/grading_config/%s/%s" % (BROADWAY_API_URL, cid, aid), headers=HEADERS,
							 json=config)

		if resp.status_code != 200:
			ret_data = resp.json()
			
			if isinstance(ret_data["data"], str):
				msg = ret_data["data"]
			else:
				msg = ret_data["data"]["message"]

			return "{}: {}".format(resp.status_code, msg)
		
		return None
	except Exception as e:
		logging.error("set_assignment_config(cid={}, aid={}, config={}): {}".format(cid, aid, config, repr(e)))
		return "Failed to decode server response"


def get_grading_run_job_id(cid, run_id):
	try:
		resp = requests.get(url="%s/grading_run_status/%s/%s" % (BROADWAY_API_URL, cid, run_id), headers=HEADERS)
		student_jobs_dict = resp.json()["data"]["student_jobs_state"]
		return list(student_jobs_dict.keys())[0]
	except Exception as e:
		logging.error("get_grading_run_job_id(cid={}, run_id={}): {}".format(cid, run_id, repr(e)))
		return None


def get_grading_job_log(cid, job_id):
	try:
		resp = requests.get(url="%s/grading_job_log/%s/%s" % (BROADWAY_API_URL, cid, job_id), headers=HEADERS)
		return resp.json()["data"]
	except Exception as e:
		logging.error("get_grading_job_log(cid={}, job_id={}): {}".format(cid, job_id, repr(e)))
		return None


def get_grading_run_log(cid, run_id):
	job_id = get_grading_run_job_id(cid, run_id)
	if job_id is None:
		return None
	log = get_grading_job_log(cid, job_id)
	return log if log is not None else None


def get_workers(cid):
	try:
		resp = requests.get(url="%s/worker/%s/all" % (BROADWAY_API_URL, cid), headers=HEADERS)
		return resp.json()["worker_nodes"]
	except Exception as e:
		logging.error("get_workers(cid={}): {}".format(cid, repr(e)))
		return None
