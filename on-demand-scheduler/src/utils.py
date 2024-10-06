import requests
import logging
from config import ON_DEMAND_URL

def trigger_run(course_id, assignment_id, scheduled_run_id, token):
    url = f"{ON_DEMAND_URL}/on-demand/api/{course_id}/{assignment_id}/trigger_scheduled_run/{scheduled_run_id}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.post(url, headers=headers)

    if res.ok:
        logging.info(f"Successfully triggered scheduled run at {url}")
    else:
        logging.warn(f"Failed to trigger scheduled run at {url}: {res.content}")

def contains_job(scheduler, job_id):
    for j in scheduler.get_jobs():
        if j.id == job_id:
            return True
    return False
