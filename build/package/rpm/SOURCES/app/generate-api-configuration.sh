#!/bin/bash -e

if [ -f /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env ]; then
  source /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env
fi

if [ "$(cat /SevOne.masterslave.master)" = "0" ]; then
  echo "Please run $0 from the master of the peer! This appliance is currently the secondary in this peer..."
  exit 1
fi

read -r PEERIP PRIMARYIP SECONDARYIP < <(/usr/local/scripts/mysqlconfig -sNe "select ip_normalize(ip) as ip, ip_normalize(primary_ip) as primary_ip, ip_normalize(secondary_ip) as secondary_ip  from peers where server_id=$(/usr/local/scripts/mysqldata -sNe 'select value from local.settings where setting="server_id"')")

API_HOST=$(/usr/local/scripts/SevOne-peer-list --master)
API_HOST="${API_HOST%"${API_HOST##*[![:space:]]}"}"
API_TOKEN_APPNAME="APPNAMEREPLACE_$(hostname -f)"

if [ ! -z ${SEVONE_API_TOKEN} ]; then
  PEERLIST_TEST=$(curl -s -k -X GET --header "Content-Type: application/json" --header "Accept: application/json" --header "X-AUTH-TOKEN: ${SEVONE_API_TOKEN}" "https://${API_HOST}/api/v2/peers" | jq -r '.title')
  if [ "${PEERLIST_TEST}" = "Unauthorized" ]; then
    unset SEVONE_API_TOKEN
  fi
fi

if [ -z ${SEVONE_API_TOKEN} ]; then
  echo "Generating API token for APPNAMEREPLACE running on host: $(hostname -f)"
  echo ""
  echo "Please enter the number of years that the token should be valid for (default: 1):"
  read -r API_TOKEN_EXPIRE < /dev/tty
  if [ -z "${API_TOKEN_EXPIRE}" ]; then
    API_TOKEN_EXPIRE=1
  fi
  echo ""
  echo 'Please enter your API username to use with APPNAMEREPLACE'
  read -r API_USERNAME < /dev/tty
  echo 'Please enter your API password (input will be hidden!)'
  read -sr API_PASSWORD < /dev/tty

  API_EXPIRATION=$((($(date +%s)+(API_TOKEN_EXPIRE*365*24*60*60))*1000))

  TMP_TOKEN=$(curl -s -k -X POST --header "Content-Type: application/json" --header "Accept: application/json" -d "{
    \"name\": \"${API_USERNAME}\",
    \"password\": \"${API_PASSWORD}\"
  }" "https://${API_HOST}/api/v2/authentication/signin?nmsLogin=false" | jq -r '.token')

  API_TOKEN=$(curl -s -k -X POST --header "Content-Type: application/json" --header "Accept: application/json" --header "X-AUTH-TOKEN: ${TMP_TOKEN}" -d "{
    \"applicationName\": \"${API_TOKEN_APPNAME}\",
    \"expirationDate\": ${API_EXPIRATION}
  }" "https://${API_HOST}/api/v2/users/api-keys" | jq -r '.apiKey')

  if [ "${API_TOKEN}" = "null" ]; then
    echo "Unable to generate token. Please check the details and try again!"
  elif [ -f /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env ]; then
    /bin/sed -i "s,SEVONE_API_TOKEN=.*,SEVONE_API_TOKEN=${API_TOKEN},g" /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env
  else
    echo ""
    echo "New token generated for APPNAMEREPLACE on host $(hostname -f)"
    echo "Please add: 'SEVONE_API_TOKEN=${API_TOKEN}' to file: /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env"
  fi
fi


# Set the correct SEVONE_API_HOST to the IP Address
if [ -f /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env ]; then
  /bin/sed -i "s,SEVONE_API_HOST=.*,SEVONE_API_HOST=${PEERIP},g" /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env
else
  echo ""
  echo "SEVONE_API_HOST address is ${PEERIP} for APPNAMEREPLACE on host $(hostname -f)"
  echo "Please add: 'SEVONE_API_HOST=${PEERIP}' to file: /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env"
fi

# Set the correct SEVONE_API_HOST and distribute the config
/bin/sed -i "s,SEVONE_SELFMON_NAME=.*,SEVONE_SELFMON_NAME=APPNAMEREPLACE-$(/usr/local/scripts/SevOne-peer-whoami | grep Name | awk {'print $3'}),g" /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env
if [ -z ${PEERIP} ] || [ -z ${PRIMARYIP} ] || [ -z ${SECONDARYIP} ]; then
  echo "Unable to determine API Addresses!"
  exit 2
fi

if [ "${PEERIP}" = "${PRIMARYIP}" ] && [ "${SECONDARYIP}" != "NULL" ]; then
  ssh -q ${SECONDARYIP} "[[ -f /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env ]]" && \
  cp /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env /tmp/.ibm-el-APPNAMEREPLACE.env && \
  /bin/sed -i "s,SEVONE_API_HOST=.*,SEVONE_API_HOST=${SECONDARYIP},g" /tmp/.ibm-el-APPNAMEREPLACE.env && \
  scp -q /tmp/.ibm-el-APPNAMEREPLACE.env ${SECONDARYIP}:/opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env && \
  rm /tmp/.ibm-el-APPNAMEREPLACE.env
elif [ "${PEERIP}" = "${SECONDARYIP}" ] && [ "${PRIMARYIP}" != "NULL" ]; then
  ssh -q ${PRIMARYIP} "[[ -f /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env ]]" && \
  cp /opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env /tmp/.ibm-el-APPNAMEREPLACE.env && \
  /bin/sed -i "s,SEVONE_API_HOST=.*,SEVONE_API_HOST=${PRIMARYIP},g" /tmp/.ibm-el-APPNAMEREPLACE.env && \
  scp -q /tmp/.ibm-el-APPNAMEREPLACE.env ${PRIMARYIP}:/opt/IBM/expert-labs/APPNAMEREPLACE/env/.ibm-el-APPNAMEREPLACE.env && \
  rm /tmp/.ibm-el-APPNAMEREPLACE.env
fi

exit 0