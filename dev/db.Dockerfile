FROM mongo:4.0

ADD test_data.zip test_data.zip
ADD load_db.sh load_db.sh

# Override the base ENTRYPOINT and CMD
ENTRYPOINT load_db.sh