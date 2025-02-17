#!/bin/bash -e

## container image configuration
APPNAME=${APPNAME:-APPNAMEREPLACE}
#USERID=${USERID:-USERIDREPLACE}
CONTAINERIMAGE=${CONTAINERIMAGE:-CONTAINERIMAGEREPLACE}
CONTAINERIMAGEVERSION=${CONTAINERIMAGEVERSION:-CONTAINERIMAGEVERSIONREPLACE}
CONTAINERENVFILE=${CONTAINERENVFILE:-/opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env}

PULL_POLICY=${PULL_POLICY:-IfNotPresent}

CONTAINER_FLAGS="${CONTAINER_FLAGS} --name ${APPNAME} --user $(id -u ingestion):$(id -g ingestion)"

## Collector Directory Mappings
CONTAINER_VOLUMES="${CONTAINER_VOLUMES} \
  -v /opt/IBM/expert-labs/APPNAMEREPLACE/etc:/opt/collector/etc \
  -v /var/log/IBM/expert-labs/APPNAMEREPLACE:/var/log/collector \
  -v /var/log/IBM/expert-labs/APPNAMEREPLACE:/opt/collector/log
"

## container log configuration
LOG_MAX_SIZE=${LOG_MAX_SIZE:-20m}
LOG_MAX_FILES=${LOG_MAX_FILES:-10}

## container resource limit configuration
MAX_MEMORY_PERCENT=${MAX_MEMORY_PERCENT:-10}
MAX_CPU_PERCENT=${MAX_CPU_PERCENT:-10}

if [ -z ${MAX_MEMORY_KB} ]; then
  MAX_MEMORY_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  let MAX_MEMORY_KB*=${MAX_MEMORY_PERCENT} MAX_MEMORY_KB/=100
fi
if [ -z ${MAX_CPU} ]; then
  MAX_CPU=$(nproc)
  # 100000 is 100 millicpu just like kubernetes does
  let MAX_CPU*=100000 MAX_CPU*=${MAX_CPU_PERCENT} MAX_CPU/=100
fi

CONTAINER_FLAGS="${CONTAINER_FLAGS} --memory=${MAX_MEMORY_KB}k --cpu-period=100000 --cpu-quota=${MAX_CPU} \
  --log-opt max-size=${LOG_MAX_SIZE} --log-opt max-file=${LOG_MAX_FILES} \
  ${CONTAINER_VOLUMES}"

if [ ! -z ${CONTAINERENVFILE} ] && [ -f ${CONTAINERENVFILE} ]; then
  CONTAINER_FLAGS="${CONTAINER_FLAGS} --env-file ${CONTAINERENVFILE}"
fi

if [ "${PULL_POLICY}" = "Always" ]; then
	docker pull ${CONTAINERIMAGE}:${CONTAINERIMAGEVERSION}
else
    docker inspect --type=image ${CONTAINERIMAGE}:${CONTAINERIMAGEVERSION} > /dev/null 2>&1 || { echo "Container Image Missing: ${CONTAINERIMAGE}:${CONTAINERIMAGEVERSION}" ; exit 1; }
fi

if [ -n "${CONTAINER_NAME}" ]; then
  #try and stop the old container gracefully after 10 sec kill it
  docker stop --time 10 ${CONTAINER_NAME} || true
  #remove the old container so we can replace it
  docker rm -f ${CONTAINER_NAME} || true
  # if we are going to track this container in a pidfile get the container id
  docker run -d --name=${CONTAINER_NAME} ${CONTAINER_FLAGS} ${CONTAINERIMAGE}:${CONTAINERIMAGEVERSION}
  # tail the logs so the container's log actually goes to the expected output
  docker logs -f ${CONTAINER_NAME} &
  # track the pid of the logs which will tell us if the container is running or not
  pid=$!
  # trap signals to run a stop command that will eventually make sure that the container is killed because supervisord will kill us in 20 sec
  trap "docker stop --time 10 ${CONTAINER_NAME}" SIGTERM SIGINT SIGQUIT
  # wait for the container to stop
  while sleep 1; do
    if ! ps -p ${pid} > /dev/null; then
      break
    fi
  done
  exit 0
fi

exec docker run --rm ${CONTAINER_FLAGS} ${CONTAINERIMAGE}:${CONTAINERIMAGEVERSION} "$@"

