import requests

from config import JENKINS_API_URL
from src import db
from src.util import timestamp_to_bw_api_format, catch_request_errors
from uuid import uuid4

STUDENT_ID = "STUDENT_ID"


def build_header(cid):
    token = db.get_course(cid)["token"]
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


@catch_request_errors
def start_grading_run(cid, aid, netids, timestamp, publish, grading_run_id: str | None):
    """
    Attempt to start a grading run.
    :param cid: the course ID.
    :param aid: the assignment ID within the course.
    :param netid: an arary of student NetIDs.
    :param timestamp: the UNIX timestamp for the run due date.
    :param publish: whether this run should be published to the grade viewer
    :return: a run_id string if successful, or None otherwise.
    """
    if not grading_run_id:
        grading_run_id = str(uuid4())
    due_date_str = timestamp_to_bw_api_format(timestamp)
    payload = {
        "STUDENT_IDS": ",".join(netids),
        "TERM_ID": cid.split("-")[1],
        "DUE_DATE": due_date_str,
        "PUBLISH_TO_STUDENT": "true",
        "PUBLISH_FINAL_GRADE": "true" if publish else "false",
        "GRADING_RUN_ID": grading_run_id,
    }
    resp = requests.post(
        url=f"{JENKINS_API_URL}/job/{aid}/buildWithParameters",
        headers=build_header(cid),
        params=payload,
    )
    resp.raise_for_status()
    return grading_run_id


@catch_request_errors
def get_grading_run_details(cid, rid):
    return db.get_jenkins_run_status_all(cid, rid)


def get_grading_run_log(cid, aid, build_url, netid):
    splitted = [x for x in build_url.split("/") if x != ""]
    build_id = splitted[-1]
    url = f"{JENKINS_API_URL}/blue/rest/organizations/jenkins/pipelines/{aid}/runs/{build_id}/nodes/"
    resp = requests.get(url=url, headers=build_header(cid))
    data = resp.json()
    for entry in data:
        if entry["displayName"].startswith(netid):
            link = f"{JENKINS_API_URL}{entry['_links']['self']['href']}log"
            raw = requests.get(url=link, headers=build_header(cid))
            return raw.text


def get_workers(cid):
    hosts = []
    url = f"{JENKINS_API_URL}/computer/api/json"
    resp = requests.get(url=url, headers=build_header(cid))
    data = resp.json()
    for item in data["computer"]:
        if item["displayName"] == "Built-In Node":
            continue
        hosts.append(
            {
                "hostname": item["displayName"],
                "alive": not (item["offline"] or item["temporarilyOffline"]),
                "busy": not item["idle"],
                "responseTimeMs": item["monitorData"][
                    "hudson.node_monitors.ResponseTimeMonitor"
                ]["average"],
            }
        )
    return hosts
