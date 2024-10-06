# What is on-demand scheduler
This is a scheduler app implemented for on-demand. It's a web application that's basically a wrapper around APScheduler. The reason we use this separate application instead of directly using APScheduler is because APScheduler does not support multi-process program. So a single job might be run multiple times on a web application because there are multiple worker processes. Once APScheduler supports multi-processing, this app is no longer needed.

# Development: Getting Started
Requires `>=python3.6`. Highly recomment using virtual environment to install required packages in `requirement.txt`. Also requires flask.

Environment variable set up:
- `ONDEMAND_SYSTEM_TOKEN`: On-demand system token

How to run a development instance
```
FLASK_APP=src FLASK_ENV=development flask run -p 3000
```
