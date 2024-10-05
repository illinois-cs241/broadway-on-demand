import logging
import requests
from src import util
from http import HTTPStatus
from config import SCHEDULER_URI

class ScheduledRunStatus:
    SCHEDULED = "scheduled"
    RAN = "ran"
    FAILED = "failed"

@util.catch_request_errors
def schedule_run(time, cid, aid):
    """
    Schedule a run at some time.
    :param time: The time to schedule the run in unix timestamp
    :param cid: course id
    :param aid: assignment id
    :return: scheduled run id, an id for the run that we just scheduled. If 
        an error occurs, return None.
    """
    url = f"{SCHEDULER_URI}/api/schedule_run"
    data = {
        "time": util.timestamp_to_iso(time),
        "course_id": cid,
        "assignment_id": aid,
    }
    resp = requests.post(url=url, data=data)
    return resp.json()["scheduled_run_id"]


@util.catch_request_errors
def update_scheduled_run(scheduled_run_id, time):
    """
    Update a already scheduled run. The only parameter we can update is time.
    :return: True if the update was successful, False otherwise.
    """
    url = f"{SCHEDULER_URI}/api/{scheduled_run_id}"
    data = {
        "time": util.timestamp_to_iso(time),
    }
    resp = requests.post(url=url, data=data)
    is_success = resp.status_code == HTTPStatus.OK
    if not is_success:
        logging.warning("Failed to update scheduled run: %s", resp.text)
    return is_success


@util.catch_request_errors
def delete_scheduled_run(scheduled_run_id):
    """
    Delete a scheduled run with the given id.
    :return: True if the delete was successful, False otherwise.
    """
    url = f"{SCHEDULER_URI}/api/{scheduled_run_id}"
    resp = requests.delete(url=url)
    is_success = resp.status_code == HTTPStatus.OK
    if not is_success:
        logging.warning("Failed to delete scheduled run: %s", resp.text)
    return is_success





