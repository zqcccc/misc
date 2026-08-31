#!/bin/bash

echo "[$(date)] Deploy started" >> /opt/webhook/webhook.log

docker compose pull
# 清理已从编排中下线的旧服务（如 trhrp-data）。
docker compose up -d --remove-orphans

echo "[$(date)] Deploy finished" >> /opt/webhook/webhook.log
