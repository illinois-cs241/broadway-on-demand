#!/bin/bash
# NEED TO RUN AS ROOT

INSTALL_DIR="/srv"
VENV_NAME="venv"

# Install python and related packages
apt-get install python3 python3-venv

# Default location for broadway-on-demand is /srv
cp -r . $INSTALL_DIR/broadway-on-demand/
cd $INSTALL_DIR/broadway-on-demand/

# Setup venv
cd src/
python3 -m venv ./$VENV_NAME
source ./$VENV_NAME/bin/activate

# Install python dependencies
python3 -m pip install -r requirements.txt
python3 -m pip install gunicorn

# Setup config file
# CHANGE THIS
# cp sample_config.py config.py

# Setup systemd service
cd ..
cp broadway-on-demand.service /etc/systemd/system/
systemctl enable broadway-on-demand
systemctl start broadway-on-demand
