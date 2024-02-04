import logging
import requests
from http import HTTPStatus
from datetime import datetime as dt

from config import (
	GHE_API_URL, TZ
)

logger = logging.getLogger(__name__)

ACCEPT_JSON = {"Accept": "application/json"}


def get_login(access_token):
	try:
		resp = requests.get("%s/user" % GHE_API_URL, headers={"Authorization": "token {}".format(access_token)})
		return resp.json()["login"].lower()
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None


def get_latest_commit(netid, access_token, github_org, github_repo_prefix):
	latest_commit = {"message": "An error occurred", "sha": "", "url": ""}

	# retrieve all student repo commits
	commits_url = f"{GHE_API_URL}/repos/{github_org}/{github_repo_prefix}_{netid}/commits"
	commits_url += "?until=" + dt.now(tz=TZ).isoformat()
	try:
		response = requests.get(commits_url, headers={"Authorization": "token {}".format(access_token)})
	except requests.exceptions.RequestException as ex:
		logger.error("Failed to fetch student commits\n{}".format(str(ex)))
		return latest_commit
	if response.status_code == HTTPStatus.NOT_FOUND or response.status_code == HTTPStatus.CONFLICT:
		# failure due to student error
		latest_commit["message"] = (
			"No commits found. Is your repo configured properly?"
		)
		return latest_commit
	if response.status_code != HTTPStatus.OK:
		logger.error("Failed to fetch latest commit for %s:\n%s", netid, response.text)
		return latest_commit

	commits = response.json()
	if len(commits) == 0:
		latest_commit["message"] = "No commits found"
	else:
		latest_raw_commit = commits[0]
		latest_commit["message"] = latest_raw_commit["commit"]["message"]
		latest_commit["sha"] = latest_raw_commit["sha"]
		latest_commit["url"] = latest_raw_commit["html_url"]
	return latest_commit
