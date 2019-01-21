from datetime import datetime

from jinja2 import Markup
from pytz import utc

from src.config import TZ


class TemplateFilters:
	def __init__(self, app):
		@app.template_filter("fmt_timestamp")
		def _filter_fmt_timestamp(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			return Markup(dt.strftime("%Y-%m-%d %H:%M"))

		@app.template_filter("fmt_timestamp_full")
		def _filter_fmt_timestamp_full(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			return Markup(dt.strftime("%Y-%m-%d %H:%M:%S.") + dt.strftime("%f")[0:3])
