docker-entrypoint.sh mongod &

# Give db some time to start
sleep 3

unzip test_data.zip && mongorestore test_data && rm -rf test_data