FROM python:3.12-alpine
WORKDIR /srv/cs341/broadway-on-demand
RUN apk add --no-cache gcc musl-dev linux-headers libffi-dev curl
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT [ "./entrypoint.sh" ]
