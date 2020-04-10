import logging
import requests
from http import HTTPStatus
from datetime import datetime as dt

from config import (
	GHE_OAUTH_URL, GHE_API_URL, GHE_CLIENT_ID, GHE_CLIENT_SECRET, DEV_MODE, DEV_MODE_LOGIN, TZ
)

logger = logging.getLogger(__name__)

ACCEPT_JSON = {"Accept": "application/json"}
RELEASE_REPO = "_release"


def get_access_token(code):
	data = {
		"client_id": GHE_CLIENT_ID,
		"client_secret": GHE_CLIENT_SECRET,
		"code": code
	}
	try:
		resp = requests.post("%s/access_token" % GHE_OAUTH_URL, json=data, headers=ACCEPT_JSON)
		return resp.json()["access_token"]
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None


def get_login(access_token):
	try:
		resp = requests.get("%s/user" % GHE_API_URL, params={"access_token": access_token})
		return resp.json()["login"]
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None


def get_latest_commit(netid, access_token, course):
	if DEV_MODE:
		return {"message": "This is a test commit.", "sha": "2db06991c7846ade1b505e80fbaf257e034c4bd5", "url": "https://github.com/illinois-cs241/broadway-on-demand"}

	latest_commit = {"message": "An error occurred", "sha": "", "url": ""}

	# retrieve all student repo commits (to master)
	commits_url = "{}/repos/{}/{}/commits".format(GHE_API_URL, course, netid)
	commits_url += "?until=" + dt.now(tz=TZ).isoformat()
	commits_url += "&sha=master"
	try:
		response = requests.get(commits_url, params={"access_token": access_token})
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
	latest_raw_commit = commits[0]
	latest_commit["message"] = latest_raw_commit["commit"]["message"]
	latest_commit["sha"] = latest_raw_commit["sha"]
	latest_commit["url"] = latest_raw_commit["html_url"]
	return latest_commit
