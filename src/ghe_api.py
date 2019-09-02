import logging
import requests
from datetime import datetime as dt

from config import (
	GHE_OAUTH_URL, GHE_API_URL, GHE_CLIENT_ID, GHE_CLIENT_SECRET, DEV_MODE, DEV_MODE_LOGIN, TZ
)

logger = logging.getLogger(__name__)

ACCEPT_JSON = {"Accept": "application/json"}
RELEASE_REPO = "_release"


def get_access_token(code):
	if DEV_MODE:
		return "some_token"
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
	if DEV_MODE:
		return DEV_MODE_LOGIN
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

	# retrieve all release repo commits (to master) SHAs
	release_commits_url = "{}/repos/{}/{}/commits".format(GHE_API_URL, course, RELEASE_REPO)
	release_commits_url += "?sha=master"
	try:
		release_commits_result = requests.get(release_commits_url, params={"access_token": access_token})
	except requests.exceptions.RequestException as ex:
		logger.error("Failed to fetch release commits\n{}".format(str(ex)))
		return latest_commit
	if release_commits_result.status_code != 200:
		logger.error("Failed to fetch release commits\n{}".format(release_commits_result.text))
		return latest_commit

	release_commits_sha = set()
	release_commits = release_commits_result.json()
	for release_commit in release_commits:
		release_commits_sha.add(release_commit["sha"])

	# retrieve all student repo commits (to master)
	commits_url = "{}/repos/{}/{}/commits".format(GHE_API_URL, course, netid)
	commits_url += "?until=" + dt.now(tz=TZ).isoformat()
	commits_url += "&sha=master"

	try:
		response = requests.get(commits_url, params={"access_token": access_token})
	except requests.exceptions.RequestException as ex:
		logger.error("Failed to fetch student commits\n{}".format(str(ex)))
		return latest_commit
	if response.status_code == 404 or response.status_code == 409:
		# failure due to student error
		latest_commit["message"] = (
			"No commits found. Is your repo configured properly?"
		)
		return latest_commit
	if response.status_code != 200:
		logger.error("Failed to fetch latest commit for %s:\n%s", netid, response.text)
		return latest_commit

	commits = response.json()
	latest_raw_commit = None
	if len(commits) == 1:
		# student has only one commit before now, so we'll use that
		latest_raw_commit = commits[0]
	for commit in commits:
		# the student has multiple commits, make sure
		# we don't grade one of the deploy commits
		if commit["sha"] not in release_commits_sha:
			latest_raw_commit = commit
			break

	if latest_raw_commit is None:
		latest_commit["message"] = (
			"No commits found."
		)
	else:
		latest_commit["message"] = latest_raw_commit["commit"]["message"]
		latest_commit["sha"] = latest_raw_commit["sha"]
		latest_commit["url"] = latest_raw_commit["html_url"]
	return latest_commit
