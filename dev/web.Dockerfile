FROM python:3.7-alpine

ARG DEP_DIR /opt/broadway-on-demand
ARG CODE_DIR /srv/broadway-on-demand

# Change to dependency directory

RUN echo $DEP_DIR
RUN echo $CODE_DIR

WORKDIR ${DEP_DIR}
RUN apk add --no-cache gcc musl-dev linux-headers libffi-dev
COPY requirements.txt requirements.txt
RUN python3 -m venv ./env
RUN source ./env/bin/activate && pip install -r requirements.txt

# Change to the code directory for development
WORKDIR ${CODE_DIR}
EXPOSE 5000
ENV FLASK_APP=src
ENV FLASK_ENV=development
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_DEBUG="true"
ENV PATH=${DEP_DIR}/env/bin
CMD flask run