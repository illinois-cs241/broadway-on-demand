import logging
import requests
from http import HTTPStatus

from ansi2html import Ansi2HTMLConverter
from json.decoder import JSONDecodeError

from config import JENKINS_API_URL
from src import db
from src.util import timestamp_to_bw_api_format, catch_request_errors
from uuid import uuid4

STUDENT_ID = "STUDENT_ID"

def build_header(cid):
	token = db.get_course(cid)["token"]
	return {"Authorization": f"Bearer {token}"}


@catch_request_errors
def start_grading_run(cid, aid, netids, timestamp, publish):
	"""
	Attempt to start a grading run.
	:param cid: the course ID.
	:param aid: the assignment ID within the course.
	:param netid: an arary of student NetIDs.
	:param timestamp: the UNIX timestamp for the run due date.
	:param publish: whether this run should be published to the grade viewer
	:return: a run_id string if successful, or None otherwise.
	"""
	grading_run_id = str(uuid4())
	due_date_str = timestamp_to_bw_api_format(timestamp)
	payload = {
		"STUDENT_IDS": ",".join(netids),
		"TERM_ID": cid.split("_")[1], 
		"DUE_DATE": due_date_str, 
		"PUBLISH_TO_STUDENT": "true", 
		"PUBLISH_FINAL_GRADE": "true" if publish else "false",
		"GRADING_RUN_ID": grading_run_id
	}
	resp = requests.post(url=f"{JENKINS_API_URL}/job/{aid}/buildWithParameters", headers=build_header(cid), params=payload)
	resp.raise_for_status()
	return grading_run_id

def get_assignment_config(*args, **kwargs):
	return None


def set_assignment_config(*args, **kwargs):
	return "200: Jenkins No-Op"


def get_grading_job_log(*args, **kwargs):
	return {"stdout": f"To view the job logs, please go to Jenkins at {JENKINS_API_URL} and view the logs there.", "stderr": ""}

@catch_request_errors
def get_grading_run_details(cid, run_id):
	return []
	# Get all environment variables for this run
	# resp = requests.get(url=f"{BROADWAY_API_URL}/grading_run_env/{cid}/{run_id}", headers=build_header(cid))
	# student_env_data = resp.json()["data"]["student_env"]
	# detail_data = []
	# # Extract job id and student id pairs from environment variable
	# for job_id, env_data in student_env_data.items():
	# 	if STUDENT_ID not in env_data:
	# 		netid = STUDENT_ID + " not found in grading env"
	# 	else:
	# 		# Each env var is a list, but it will most likely only have 1 entry
	# 		netid = ", ".join(env_data[STUDENT_ID])
	# 	detail_data.append({"jobId": job_id, "netid": netid})
	# return detail_data


def get_grading_run_log(cid, run_id):
	return get_grading_job_log()

def get_workers(cid):
	return None