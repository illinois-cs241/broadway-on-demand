import logging
import requests
from http import HTTPStatus

from ansi2html import Ansi2HTMLConverter
from json.decoder import JSONDecodeError

from config import BROADWAY_API_URL
from src import db
from src.util import timestamp_to_bw_api_format, catch_request_errors


def build_header(cid):
	token = db.get_course(cid)["token"]
	return {"Authorization": f"Bearer {token}"}


@catch_request_errors
def start_grading_run(cid, aid, netids, timestamp):
	"""
	Attempt to start a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param netid: an arary of student NetIDs.
	:param timestamp: the UNIX timestamp for the run due date.
	:return: a run_id string if successful, or None otherwise.
	"""
	due_date_str = timestamp_to_bw_api_format(timestamp)
	students_env = [
		{
			"STUDENT_ID": netid,
			"DUE_DATE": due_date_str,
		} for netid in netids
	]
	data = {
		"students_env": students_env
	}
	resp = requests.post(url=f"{BROADWAY_API_URL}/grading_run/{cid}/{aid}", headers=build_header(cid), json=data)
	run_id = resp.json()["data"]["grading_run_id"]
	return run_id


def get_grading_run_status(cid, run_id):
	"""
	Get the status of a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param run_id: the run ID received when the run was started.
	:return: a status string if successful, or None otherwise.
	"""
	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_run_status/{cid}/{run_id}", headers=build_header(cid))
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


def get_grading_job_queue_position(cid, run_id):
	"""
	Get the queue position of a grading run.
	:param cid: the course ID.
	:param run_id: the run ID received when the run was started.
	:return: the queue position as a string if successful, or None otherwise.
	"""
	try:
		job_id = get_grading_run_job_id(cid, run_id)
		if job_id == None:
			return None
		resp = requests.get(url=f"{BROADWAY_API_URL}/queue/{cid}/{job_id}/position", headers=build_header(cid))
		queue_position = resp.json()["data"]["position"]
		return str(queue_position)
	except requests.exceptions.RequestException as e:
		logging.error(f"get_grading_job_queue_position(cid={cid}, run_id={run_id}): {repr(e)}")
		return None
	except KeyError as e:
		logging.error(f"get_grading_job_queue_position(cid={cid}, run_id={run_id}): {repr(e)}")
		return None
	except JSONDecodeError as e:
		logging.error(f"get_grading_job_queue_position(cid={cid}, run_id={run_id}): {repr(e)}")
		return None


def get_assignment_config(cid, aid):
	"""
	Get run config for an assignment
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	"""

	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_config/{cid}/{aid}", headers=build_header(cid))

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
		resp = requests.post(url=f"{BROADWAY_API_URL}/grading_config/{cid}/{aid}", headers=build_header(cid), json=config)

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
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_run_status/{cid}/{run_id}", headers=build_header(cid))
		student_jobs_dict = resp.json()["data"]["student_jobs_state"]
		# TODO: might return an empty dict
		return list(student_jobs_dict.keys())[0]
	except Exception as e:
		logging.error(f"get_grading_run_job_id(cid={cid}, run_id={run_id}): {repr(e)}")
		return None


def get_grading_job_log(cid, job_id):
	try:
		resp = requests.get(url=f"{BROADWAY_API_URL}/grading_job_log/{cid}/{job_id}", headers=build_header(cid))
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
		resp = requests.get(url=f"{BROADWAY_API_URL}/worker/{cid}/all", headers=build_header(cid))
		return resp.json()["data"]["worker_nodes"]
	except Exception as e:
		logging.error(f"get_workers(cid={cid}): {repr(e)}")
		return None
