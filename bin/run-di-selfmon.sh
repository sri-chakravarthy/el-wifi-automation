#!/bin/bash
export HOST_IP=$(hostname -I | awk '{print $1}')
export HOST_NAME=$(hostname)
docker-compose -f /opt/sevone-uc/ps-di-selfmon/docker-compose.yml up -d