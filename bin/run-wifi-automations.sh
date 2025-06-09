#!/bin/bash
APP_NAME="APPNAMEREPLACE"
IMAGE_NAME="CONTAINERIMAGEREPLACE:CONTAINERIMAGEVERSIONREPLACE"
HOST_IP=${HOST_IP}



/usr/bin/podman run --rm \
  --name "$APP_NAME" \
  --user 0:0 \
  --memory 801337k \
  --log-driver=json-file \
  --log-opt max-size=20m \
  --log-opt max-file=10 \
  -v /var/custom/ps-addon/$APP_NAME/etc:/app/etc \
  -v /var/custom/ps-addon/$APP_NAME/env:/app/env \
  -v /var/custom/ps-addon/$APP_NAME/bin:/app/bin \
  -v /var/custom/ps-addon/$APP_NAME/log:/app/log \
  -v /root/.ssh/id_rsa:/app/.ssh/id_rsa:ro \
  -e HOST_IP="$HOST_IP" \
  --restart=on-failure \
  "$IMAGE_NAME"