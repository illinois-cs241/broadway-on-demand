import os
from pytz import utc
from flask import Flask, Blueprint

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore

from config import *
from src.routes import Routes

token = os.environ["ONDEMAND_SYSTEM_TOKEN"]

scheduler = BackgroundScheduler(timezone=utc)
jobstore = MongoDBJobStore(database=JOBSTORE_DB, collection=JOBSTORE_COLLECTION)
scheduler.add_jobstore(jobstore)
scheduler.start()

app = Flask(__name__)

blueprint = Blueprint("on-demand-scheduler", __name__, url_prefix=BASE_URL)
Routes(blueprint, scheduler, token)

app.register_blueprint(blueprint)
