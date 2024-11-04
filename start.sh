#!/usr/bin/bash

service cron start

sleep 1

echo "*/5 * * * * /scripts/update-conf.py " > /tmp/cron
crontab /tmp/cron


python main.py 

