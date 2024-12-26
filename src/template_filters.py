from datetime import datetime

from jinja2 import Markup
from pytz import utc

from config import TZ
from src.util import timestamp_round_up_minute


class TemplateFilters:
	def __init__(self, app):
		@app.template_filter("round_timestamp")
		def _filter_round_timestamp(timestamp):
			return timestamp_round_up_minute(timestamp)

		@app.template_filter("fmt_timestamp")
		def _filter_fmt_timestamp(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			return Markup(dt.strftime("%Y-%m-%d %H:%M"))

		@app.template_filter("fmt_timestamp_full")
		def _filter_fmt_timestamp_full(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			return Markup(dt.strftime("%Y-%m-%d %H:%M:%S.") + dt.strftime("%f")[0:3])

		@app.template_filter("fmt_datetime_local")
		def _filter_fmt_datetime_local(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			return Markup(dt.strftime("%Y-%m-%dT%H:%M"))

		@app.template_filter("fmt_timestamp_human")
		def _filter_fmt_timestamp_human(timestamp):
			dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=utc).astimezone(TZ)
			# Format: Tue, Sep 10, 2024, 12:30pm (CDT)
			time_str = dt.strftime("%a, %b %-d, %Y, %-I:%M %p")
			return Markup(time_str)