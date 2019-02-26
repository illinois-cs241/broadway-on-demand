from pytz import timezone

DEV_MODE = False

TZ = timezone("America/Chicago")

BASE_URL = "/on-demand"

SESSION_TYPE = "mongodb"
SESSION_MONGODB = "localhost:27017"
SESSION_MONGODB_DB = "flask_session"

MONGO_URI = "mongodb://localhost:27017/broadway_on_demand"
BROADWAY_API_URL = "http://some.host/api/v1"
BROADWAY_API_TOKEN = "some_token"

SYSTEM_API_TOKEN = "some_token"

GHE_CLIENT_ID = "some_client_id"
GHE_CLIENT_SECRET = "some_client_secret"
GHE_OAUTH_URL = "https://some.host/login/oauth"
GHE_LOGIN_URL = "%s/authorize?client_id=%s" % (GHE_OAUTH_URL, GHE_CLIENT_ID)
GHE_API_URL = "https://some.host/api/v3"
