from pytz import timezone

# When True, routes with the util.disable_in_maintenance_mode decorator will return a static page with the message below.
MAINTENANCE_MODE = False
# Message to show when in maintenance mode; appended to "Broadway on Demand is currently under maintenance."
MAINTENANCE_MODE_MESSAGE = "Maintenance will conclude at __:__ on __/__."

# When true, GitHub Enterprise login can be bypassed to log in as the username below.
DEV_MODE = False

# Server time zone, used for displaying times and specifying due date for Broadway API.
TZ = timezone("America/Chicago")

# The base URL used for all routes in the app.
BASE_URL = "/on-demand"

# Flask-Session configuration. See https://pythonhosted.org/Flask-Session/
SESSION_TYPE = "mongodb"
SESSION_MONGODB = "localhost:27017"
SESSION_MONGODB_DB = "flask_session"

# MongoDB URI for Broadway on Demand data.
MONGO_URI = "mongodb://localhost:27017/broadway_on_demand"

# Scheduler URI for scheduling runs
SCHEDULER_URI = "http://localhost:3000/scheduler"

# Broadway API configuration.
BROADWAY_API_URL = "http://some-broadway-api-server.example/api/v1"

# API token used to authenticate /system/ routes.
SYSTEM_API_TOKEN = "some_token"

# GitHub API base URL.
GHE_API_URL = "https://api.github.com"

# Microsoft Azure auth config
AUTH_DOMAIN = "some auth domain like `example.edu`"
MIP_SCOPES = ["email"]
MIP_AUTHORITY = "some authority or `https://login.microsoftonline.com/common` for multi-tenant world-wide cloud"
MIP_CLIENT_ID = "some_client_id"
MIP_CLIENT_SECRET = "some_client_secret"
