# Broadway on Demand

### Developer setup

- Install and start [MongoDB Server](https://www.mongodb.com/download-center/community).
- Clone the repository and `cd` into the repository root.
- Make a copy of the sample config file: `cp sample_config.py config.py`.
- Set `DEV_MODE = True` in `config.py`.
- (recommended) Create and activate a Python 3 virtualenv: `python3 -m virtualenv venv && source venv/bin/activate`
  - You may need to install `virtualenv` with `pip3 install virtualenv`.
- Install dependencies: `pip install -r requirements.txt`.
- Run the development server: `FLASK_APP=src FLASK_ENV=development flask run`. The server will run at `localhost:5000` by default.
- To log in while in dev mode, navigate to `http://localhost:5000/on-demand/login/ghe_callback/?code=x`. You will be logged in as the user defined in the `DEV_MODE_LOGIN` config field.
