#!/usr/bin/bash

service cron start

sleep 1

#echo "*/5 * * * * /app/update-conf.py " # date >> /tmp/updates.log && curl --location --request POST 'http://localhost:8000/api/import-xml' --data '' >> /tmp/updates.log && echo "\n" >> /tmp/updates.log" > /tmp/cron
echo "*/5 * * * * /scripts/update-conf.py " >> /tmp/cron
crontab /tmp/cron


python main.py 

