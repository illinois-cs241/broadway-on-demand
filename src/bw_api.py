import logging
import requests
from http import HTTPStatus

from ansi2html import Ansi2HTMLConverter
from json.decoder import JSONDecodeError

from config import BROADWAY_API_TOKEN, BROADWAY_API_URL
from src.util import timestamp_to_bw_api_format

HEADERS = {"Authorization": f"Bearer {BROADWAY_API_TOKEN}" }


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
		resp = requests.post(url=f"{BROADWAY_API_URL}/grading_run/{cid}/{aid}", headers=HEADERS, json=data)
		run_id = resp.json()["data"]["grading_run_id"]
		return run_id
	except requests.exceptions.RequestException as e:
		logging.error(f"start_grading_run(cid={cid}, aid={aid}, netid={netid}): {repr(e)}")
		return None
	except KeyError as e:
		logging.error(f"start_grading_run(cid={cid}, aid={aid}, netid={netid}): {repr(e)}")
		return None
	except JSONDecodeError as e:
		logging.error(f"start_grading_run(cid={cid}, aid={aid}, netid={netid}): {repr(e)}")
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
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_run_status/{cid}/{run_id}", headers=HEADERS)
		student_jobs_dict = resp.json()["data"]["student_jobs_state"]
		return list(student_jobs_dict.values())[0]
	except requests.exceptions.RequestException as e:
		logging.error(f"get_grading_run_status(cid={cid}, run_id={run_id}): {repr(e)}")
		return None
	except KeyError as e:
		logging.error(f"get_grading_run_status(cid={cid}, run_id={run_id}): {repr(e)}")
		return None
	except JSONDecodeError as e:
		logging.error(f"get_grading_run_status(cid={cid}, run_id={run_id}): {repr(e)}")
		return None


def get_assignment_config(cid, aid):
	"""
	Get run config for an assignment
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	"""

	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_config/{cid}/{aid}", headers=HEADERS)

		if resp.status_code == HTTPStatus.OK:
			ret_data = resp.json()
			return ret_data["data"]
	except Exception as e:
		logging.error(f"get_assignment_config(cid={cid}, aid={aid}): {repr(e)}")

	return None


def set_assignment_config(cid, aid, config):
	"""
	Set run config for an assignment. Return error message if failed
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param config: assignemnt config(pre-processing pipeline, student pipelines, etc.)
	"""

	try:
		resp = requests.post(url=f"{BROADWAY_API_URL}/grading_config/{cid}/{aid}", headers=HEADERS, json=config)

		if resp.status_code != HTTPStatus.OK:
			ret_data = resp.json()

			if isinstance(ret_data["data"], str):
				msg = ret_data["data"]
			else:
				msg = ret_data["data"]["message"]

			return f"{resp.status_code}: {msg}"

		return None
	except Exception as e:
		logging.error(f"set_assignment_config(cid={cid}, aid={aid}, config={config}): {repr(e)}")
		return "Failed to decode server response"


def get_grading_run_job_id(cid, run_id):
	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_run_status/{cid}/{run_id}", headers=HEADERS)
		student_jobs_dict = resp.json()["data"]["student_jobs_state"]
		# TODO: might return an empty dict
		return list(student_jobs_dict.keys())[0]
	except Exception as e:
		logging.error(f"get_grading_run_job_id(cid={cid}, run_id={run_id}): {repr(e)}")
		return None


def get_grading_job_log(cid, job_id):
	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_job_log/{cid}/{job_id}", headers=HEADERS)
		log = resp.json()["data"]
		if log:
			converter = Ansi2HTMLConverter()
			log["stdout"] = converter.convert(log.get("stdout"), full=False)
			log["stderr"] = converter.convert(log.get("stderr"), full=False)
		return log
	except Exception as e:
		logging.error(f"get_grading_job_log(cid={cid}, job_id={job_id}): {repr(e)}")
		return None


def get_grading_run_log(cid, run_id):
	job_id = get_grading_run_job_id(cid, run_id)
	if job_id is None:
		return None
	log = get_grading_job_log(cid, job_id)
	return log if log is not None else None


def get_workers(cid):
	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/worker/{cid}/all", headers=HEADERS)
		return resp.json()["data"]["worker_nodes"]
	except Exception as e:
		logging.error(f"get_workers(cid={cid}): {repr(e)}")
		return None
