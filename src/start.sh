#!/bin/sh
modprobe bcm2835-v4l2

while true
do
    python3 /usr/local/src/app/http_server.py
    sleep 30
done
