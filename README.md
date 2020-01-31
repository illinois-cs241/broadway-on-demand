# Broadway on Demand

### Developer setup

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
    - non_admin (a staff, but not an admin of the test course)
    - admin (staff and admin of the test course)
