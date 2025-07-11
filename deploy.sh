#!/bin/bash

echo "[$(date)] Deploy started" >> /opt/webhook/webhook.log

docker compose pull
docker compose up -d

echo "[$(date)] Deploy finished" >> /opt/webhook/webhook.log
