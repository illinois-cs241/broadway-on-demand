FROM mongo:4.0

ENV DEBIAN_FRONTEND=noninteractive
ADD test_data.zip test_data.zip
ADD dev/load_db.sh load_db.sh
RUN chmod +x ./load_db.sh
RUN apt-get update && apt-get -y install unzip

# Override the base ENTRYPOINT and CMD
ENTRYPOINT ./load_db.sh