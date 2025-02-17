import requests
from logger_config import logger
from PasswordEncryption import *
import traceback
import os
import os.path
import base64
import time
import sys
from SevOneAppliance import *




###### Makes the script to sleep based on the interval ######
def go_to_sleep(loop_start, loop_finish,loop_count,interval):
        
    if interval == 0:
        logger.info("Finished Collection (loop " + str(loop_count)+") in " + str(
            (int(loop_finish) - int(loop_start))) + " seconds... No new loop will run since POLLING_INTERVAL or --interval was set to 0. Exiting...")
        return False
    else:
        loop_sleep = (int(interval) -
                    (int(loop_finish) - int(loop_start)))
        if (loop_sleep > 0):
            logger.info("Finished Collection (loop " + str(loop_count)+") in " + str(
                (int(loop_finish) - int(loop_start))) + " seconds... New loop in "+str(int(interval) - int(int(loop_finish) - int(loop_start)))+" seconds...")
            time.sleep(float(loop_sleep))
            return True
        else:
            logger.warning("Finished Collection (loop " + str(loop_count)+") in " + str(
                (int(loop_finish) - int(loop_start))) + " seconds... Interval Time (" + str(interval) + " seconds) exceeded!! Starting new loop immediately...")
            return True



def encode_credentials(username, password):
    credentials = f"{username}:{password}"
    credentials_bytes = credentials.encode('ascii')
    encoded_credentials_bytes = base64.b64encode(credentials_bytes)
    encoded_credentials = encoded_credentials_bytes.decode('ascii')
    return encoded_credentials



def make_api_call(ipAddress,api_url, method,token, data="",insecure=False):
    try:
        # Set up the headers with the authentication token
        headers = {
            "Content-Type": "application/json",
            'Accept': 'application/json',
            'Authorization': f'Basic {token}'
        }
        # Set up the verify parameter based on the 'insecure' flag
        verify = False if insecure else True
        url = "https://" + ipAddress + api_url

        logger.debug("Making API call")
        logger.debug("URL: " + url + ", Method: " + method + ", data: ")
        input_data = json.dumps(data)
        logger.debug(input_data)
        
        # Make the API call with the headers and SSL certificate verification option
        if method == "GET":
            response = requests.get(url, headers=headers, verify=verify)
        elif method == "POST" :
            if input_data == "":
                response = requests.post(url, headers=headers, verify=verify)
            else:
                response = requests.post(url, headers=headers, verify=verify,data=input_data)
        else:
            logger.debug("Unknown http request method passed")
        # Check if the request was successful (status code 200)
        if response.status_code == 200:

            logger.debug(f"API Call successful")
            
        else:
            # Print an error message if the request was not successful
            logger.error(f"Error: Unable to fetch data. Status code: {response.status_code}")
        return response
    except Exception as e:
        # Handle exceptions, such as network errors
        logger.error(f"An error occurred: {e}")
        return None


# Get data for each metrics

def get_data_from_metrics(ipAddress,token,query):
    method = "POST"
    api_url = "/prometheus/api/v1/query?query="+ str(query)
    
    response_data = make_api_call(ipAddress,api_url,method, token,insecure=True)    
    if response_data is not None:
        metrics_data = json.loads(response_data.text)
        # logger.debug(metrics_data)        
    else:
        metrics_data = None
        

    return metrics_data

# def body_creation (objectName, objectNames):
#     subobjectName1 = "di-asset-sweeper"
#     subobjectName2 = "di-user-sync"

#     if subobjectName1 in objectName or subobjectName2 in objectName:
#         objectName = "-1"

#     if objectName != "-1":
#         if objectName  not in objectNames:

 

if __name__ == '__main__':
    try:
        loop_count = 0
        while True:

            logger.info('-----------------------------------------------------------------------------------------------------------');
            logger.info('Starting execution of application')
            loop_start = int(time.time())
            loop_count += 1
            logger.info("Started Collection (loop " + str(loop_count) + ")")
            #file_prefix = "/app/"
            
            file_prefix = ""
            #configurationFile = "/opt/IBM/expert-labs/el-proj-templates/etc/config.json"
            #keyFile = "/opt/IBM/expert-labs/el-proj-templates/env/key.txt"
            configurationFile = file_prefix + "etc/config.json"
            keyFile = file_prefix + "env/key.txt"
            with open(keyFile,"r") as keyfile:
                key=keyfile.read()
            EncryptConfigurationFile(configurationFile,keyFile,"DIDetails","List")
            EncryptConfigurationFile(configurationFile,keyFile,"ApplianceDetails","List")
            with open(configurationFile, "r") as f:
                try:
                    config = json.load(f)
                except json.decoder.JSONDecodeError as e:
                    logger.error(f"Error loading JSON data: {e}")
                    loop_finish = time.time()                
                    # go to sleep till next poll                    
                    if go_to_sleep(loop_start, loop_finish,loop_count,config["interval"]):
                        continue
                    else:
                        break

            logger.info(config)

            for dataInsight in config["DIDetails"]:
                appPassword = dataInsight["Password"]["EncryptedPwd"].encode('utf-8')
                password=DecryptPassword(appPassword,key)
                userName = dataInsight["UserName"]
                ipAddress = dataInsight["IPAddress"]
                metrics = dataInsight["Metrics"]
                objectNames = dataInsight["objectNames"]
                deviceName = dataInsight["deviceName"]
                body = dataInsight["body"]
                
            
                        


            
                token = encode_credentials(userName, password)        
                logger.debug(f'token: {token}')
                body[deviceName] = {}

                logger.info(f"Fetching Metric data from Data Insight")
                for key, value in metrics.items():
                    objectType = key
                    
                    logger.info(f"Metrics for ObjectType: {key}")
                    for metric in value:
                        Query = metric['query']
                        if 'indicatorName' in metric:
                            logger.info(f"Indicator Name in Config: {metric['indicatorName']}")
                            indicatorName= metric['indicatorName']
                        else:
                            indicatorName = ""
                        logger.debug(f"Query: {Query}")
                        object_metrics = get_data_from_metrics (ipAddress, token, Query)
                        
                        logger.debug(f"ObjectType: {objectType}, Object_Metrics: {object_metrics}")
                        for item in object_metrics["data"]["result"]:
                            
                            if objectType == "certificate":
                                if item["metric"]["name"]:
                                    objectName = item["metric"]["name"]
                                else:
                                    objectName = "-1"
                            elif objectType == "pod":
                                if item["metric"]["pod"]:
                                    objectName = item["metric"]["pod"]
                                else:
                                    objectName = "-1"
                            elif objectType == "deployment":
                                if item["metric"]["deployment"]:
                                    objectName = item["metric"]["deployment"]
                                else:
                                    objectName = "-1"
                            elif objectType == "DiskIO":
                                 if item["metric"]["device"]:
                                     objectName = item["metric"]["device"]
                                     logger.debug(f"ObjectType:{objectType}, ObjectName:{objectName}")
                                 else:
                                     objectName = "-1"
                            elif objectType == "kube node":
                                if item["metric"]["node"]:
                                    objectName = item["metric"]["node"]
                                else:
                                    objectName = "-1"
                            elif objectType == "DI User Sessions":
                                    objectName = "DI User Sessions"
                            elif objectType == "Containers Interface":
                                if "pod" in item["metric"]:
                                    objectName = f"{item['metric']['pod']}::{item['metric']['interface']}"
                                else:
                                    objectName = "-1"
                            elif objectType == "Containers":
                                if "container" in item["metric"]:
                                    objectName = item["metric"]["container"]
                                else:
                                    objectName = "-1"
                            subobjectName1 = "di-asset-sweeper"
                            subobjectName2 = "di-user-sync"

                            if subobjectName1 in objectName or subobjectName2 in objectName:
                                objectName = "-1"
                            
                            if objectName != "-1":
                                if objectName not in objectNames:
                                    if object_metrics["data"]["result"]:
                                        timesatampVal = item["value"][0]
                                    else:
                                        timesatampVal = 0
                                    rounded_timestamp = round(timesatampVal)

                                    
                                    body[deviceName][objectName]=[
                                        objectType, 
                                            {
                                            "timestamp": {
                                                "timestamp": rounded_timestamp
                                            }
                                        }
                                    ]
                                    
                                    objectNames.append(objectName)
                                    #logger.debug(objectNames)
                                    #logger.debug(body)

                                if rounded_timestamp != 0:
                                    
                                    if indicatorName == "":
                                        indicatorName = item["metric"]["__name__"]
                                    
                                    # body[deviceName][objectName][1]["timestamp"] [indicatorName] = []
                                    body[deviceName][objectName][1]["timestamp"] [indicatorName] =[
                                        item["value"][1],
                                        metric["units"],
                                        metric["type"]
                                    ]

              
                                    #logger.debug(body)
                                    
                logger.info(f'The body is {body}')
                
                #Ingesting the metrics into SevOne Appliance
                
                ###### Check Master-Slave situation ######
                
                logger.info(f"Checking if host is PAS/HSA")
                '''
                
                with open(f'{file_prefix}SevOne.masterslave.master') as f:
                    if f.read().rstrip() == '0':
                    
                        logger.critical('loop:' + str(loop_count) + ' Running on Secondary appliance ... Skipping loop increase...')
                        loop_finish = time.time()
                        # go to sleep till next poll
                        
                        if go_to_sleep(loop_start, loop_finish,loop_count,config["interval"]):
                            continue
                        else:
                            break
                '''
                
                logger.info(f"Host is PAS. Continuing...")
                #Print appliance details
                #SevOne_appliance_obj = SevOneAppliance(config["ApplianceDetails"][0]["IPAddress"],config["ApplianceDetails"][0]["UserName"],DecryptPassword(config["ApplianceDetails"][0]["Password"]["EncryptedPwd"].encode('utf-8'),key),config["ApplianceDetails"][0]["sshUserName"],DecryptPassword(config["ApplianceDetails"][0]["sshPassword"]["EncryptedPwd"].encode('utf-8'),key))
                keyFile = file_prefix + "env/key.txt"
                with open(keyFile,"r") as keyfile:
                    key=keyfile.read()
                SevOne_appliance_obj = SevOneAppliance(config["ApplianceDetails"][0]["IPAddress"],config["ApplianceDetails"][0]["UserName"],DecryptPassword(config["ApplianceDetails"][0]["Password"]["EncryptedPwd"].encode('utf-8'),key),config["ApplianceDetails"][0]["sshUserName"],DecryptPassword(config["ApplianceDetails"][0]["sshPassword"]["EncryptedPwd"].encode('utf-8'),key),config["ApplianceDetails"][0]["UseSShKeys"])

                for deviceName,object_dictionary in body.items():
                
                    object_list= []
                    for objectName,objectDetails in object_dictionary.items(): # The ObjectNames are keys. 
                        objectDictToBeIngested = {}
                        objectType = objectDetails[0]
                        timestamp = objectDetails[1]["timestamp"]["timestamp"]
                        indicatorList = []
                        for indicatorName, indicatorDetails in objectDetails[1]["timestamp"].items():
                            if indicatorName == "timestamp":
                                continue
                            indicatorDict = {}
                            indicatorDict = {
                                "format":indicatorDetails[2],
                                "name": indicatorName,
                                "units": indicatorDetails[1],
                                "value" : indicatorDetails[0]
                            }
                            indicatorList.append(indicatorDict)
                        objectDictToBeIngested = {
                            "automaticCreation": True,
                            "description": "Created by DI SelfMon",
                            "name": objectName,
                            "pluginName": "DEFERRED",
                            "timestamps": [
                                {
                                "indicators": indicatorList,
                                "timestamp": timestamp
                                }
                            ],
                            "type": objectType
                        }
                        object_list.append(objectDictToBeIngested)
                    diIPAddress = dataInsight["IPAddress"]
                    if (":" in dataInsight["IPAddress"]):
                        diIPAddress,port = dataInsight["IPAddress"].split(":", 1)
                    result = SevOne_appliance_obj.ingest_dev_obj_ind(deviceName, diIPAddress,object_list)
                    if result==1:
                        logger.error(f"Error ingesting data into SevOne.")
                    else:
                        logger.debug(f"Result of ingestion: {result}")


            if config["interval"] == 0:
                logger.info("Finished Collection (loop " + str(loop_count)+") in " + str(
                    (int(time.time()) - int(loop_start))) + " seconds... No new loop will run since POLLING_INTERVAL or --interval was set to 0. Exiting...")
                break
            else:
                loop_sleep = (int(config["interval"]) -
                            (int(time.time()) - loop_start))
                if (loop_sleep > 0):
                    logger.info("Finished Collection (loop " + str(loop_count)+") in " + str(
                        (int(time.time()) - int(loop_start))) + " seconds... New loop in "+str(int(config["interval"]) - int(int(time.time()) - int(loop_start)))+" seconds...")
                    time.sleep(float(loop_sleep))
                else:
                    logger.warning("Finished Collection (loop " + str(loop_count)+") in " + str(
                        (int(time.time()) - int(loop_start))) + " seconds... Interval Time (" + str(config["interval"]) + " seconds) exceeded!! Starting new loop immediately...")

                if loop_count > 499:
                    #Exit container. Container restarts
                    exit(1)

            del config
            del SevOne_appliance_obj
            del appPassword ,password, userName ,ipAddress ,metrics ,objectNames ,deviceName ,body 
            del value,metric,Query, object_metrics,rounded_timestamp
            del objectDictToBeIngested,indicatorDetails,indicatorDict,indicatorList
            del body, object_dictionary,objectName,indicatorName,diIPAddress,result

        # Exit with 0 for container to not restart    
        sys.exit(0)


            
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"An unexpected error occurred: {tb}")
        #Exit container without restart
        sys.exit(0)




