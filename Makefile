format:
	ruff format
local:
	flask run --port 9001
build:
	docker build . -t ghcr.io/illinois-cs241/broadway-on-demand:latest
