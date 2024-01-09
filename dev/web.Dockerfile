FROM python:3.7-alpine

# Change to dependency directory
WORKDIR ${DEP_DIR}
RUN apk add --no-cache gcc musl-dev linux-headers
COPY requirements.txt requirements.txt
RUN python3 -m virtualenv ./env && source ./env/bin/activate
RUN pip install -r requirements.txt
ENV PATH=${DEP_DIR}/env/bin

# Change to the code directory for development
WORKDIR ${CODE_DIR}
EXPOSE 5000
ENV FLASK_APP=src
ENV FLASK_ENV=development
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_DEBUG="true"
CMD ["${DEP_DIR}/env/bin/flask", "run"]