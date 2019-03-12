import requests

from config import GHE_OAUTH_URL, GHE_API_URL, GHE_CLIENT_ID, GHE_CLIENT_SECRET, DEV_MODE

ACCEPT_JSON = {"Accept": "application/json"}


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
		return "srpatil2"
	try:
		resp = requests.get("%s/user" % GHE_API_URL, params={"access_token": access_token})
		return resp.json()["login"]
	except requests.exceptions.RequestException:
		return None
	except KeyError:
		return None
