# Deprecation Notice

We have moved to https://github.com/cs341-illinois/on-demand, which is a rewritten version 2 of Brodway On-Demand.

# Broadway on Demand

### Developer Setup (Docker Compose)

- Copy `dev/dev_config.py` to repo root as `config.py`
- Run `docker compose up`. Server runs at `localhost:3000` by default. This can be changed in the docker compose file.
- To log in, navigate to <http://localhost:3000/on-demand/login/>. You can login as any user. In the test database there are three users:
    - student (student of the test course)
    - non-admin (a staff, but not an admin of the test course)
    - admin (staff and admin of the test course)

### Developer setup (Local)

- Install and start [MongoDB Server](https://www.mongodb.com/download-center/community). To ensure that MongoDB is running, run `mongo`.
- Clone the repository and `cd` into the repository root.
- Make a copy of the sample config file: `cp sample_config.py config.py`.
- Set `DEV_MODE = True` in `config.py`.
- (recommended) Create and activate a Python 3 virtualenv: `python3 -m virtualenv venv && source venv/bin/activate`
  - You may need to install `virtualenv` with `pip3 install virtualenv`.
- Install dependencies: `pip install -r requirements.txt`.
- Run the development server: `FLASK_APP=src FLASK_ENV=development flask run`. The server will run at `localhost:5000` by default.
- To add test data to the database, unzip and restore the given dump: `unzip test_data.zip && mongorestore test_data && rm -rf test_data`
- To log in, navigate to <http://localhost:5000/on-demand/login/>. You can login as any user. In the test database there are three users:
    - student (student of the test course)
    - non-admin (a staff, but not an admin of the test course)
    - admin (staff and admin of the test course)

## How to update test database
If you change the structure of database and you want to update the distributed test_data.zip, use the following command:
```
mongodump --db broadway_on_demand --out=test_data && zip -r test_data.zip test_data && rm -r test_data
```

### New Course Setup

#### Steps
- Ask on-demand managers to add your course to the on-demand database with at least one admin.
  - Admins are able to modify roster and add assignments from the user interface.
- Obtain a username and password in Jenkins which can start jobs, read logs, etc, and set the token field equal to `base64(username:password)`.
- Create docker images for grading a single student
  - On-demand will pass in the student's netid as `STUDENT_ID` and the timestamp as `DUE_DATE` to the all grader processes.
  - The `DUE_DATE` is in the string format `YYYY-MM-DD hh:mm` in UTC time zone.
- Add an assignment with the UI
  - Assignment ID will be displayed and can not be changed once set.
  - Max Runs along with Quota Type determine how many runs student get per day or total. Note that staff members always have one run for all assignments.
  - **Given an Assignment ID in Broadway, a pipeline with the same name and accepting the requisite parameters must exist at the root parameters.** See [here](src/bw_api.py#L23) for the parameters provided to the Jenkins build job.
- Test out the assignment by going to student view and start a grading run for yourself.
  - Make sure you are added as a student to the course in order to do this.

#### Important Notes
- broadway-on-demand assumes that a student's netid is the same as the studne'ts repository name. It uses that to get a student's latest commit.
