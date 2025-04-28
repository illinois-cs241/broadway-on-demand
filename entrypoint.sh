#!/bin/sh
gunicorn --workers 5 --bind 0.0.0.0:9090 -m 007 wsgi:app
