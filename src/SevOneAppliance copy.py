import subprocess
import re
import csv
import time
from datetime import datetime
import requests
from logger_config import logger
from PasswordEncryption import *
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import xml.etree.ElementTree as ET
from xml.dom import minidom
import ipaddress
import paramiko
import traceback

class SevOneAppliance:
    def __init__(self,ipAddress,username,password,ssh_username=None,ssh_password=None,use_ssh_keys=0):
        self.IPAddress = ipAddress
        self.UserName = username
        self.Password = password
        # Get the IPADdress of the host machine
        host_ip_addr,hostname = self.get_host_details()
        #logger.debug(f"The host IPAddress: {host_ip_addr}")
        self.sshIPAddress = host_ip_addr
        self.hostname = hostname
        self.sshUserName = ssh_username
        self.sshPassword = ssh_password
        logger.debug(f"UsesshKeys={use_ssh_keys}")
        if use_ssh_keys==1:
            self.sshKeyPath = "/app/.ssh/id_rsa"
        else:
            self.sshKeyPath = None
        self.bearer_token = self.get_and_extract_auth_bearer_token()
        self.ssh_client = self.get_ssh_client()

    def get_host_details(self):
        host_ip = os.getenv('HOST_IP', '127.0.0.1')
        hostname = os.getenv('HOST_NAME', 'sevone')
        return host_ip,hostname
    
    def get_ssh_client(self):
        ssh_client = paramiko.SSHClient()
        try: 
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.info(f"HostIP: {self.sshIPAddress}")
            #logger.debug(f"{cmUserName}/{DecryptPassword(cmPassword,key)}")
            if self.sshKeyPath is None:
                logger.debug(f"Using ssh password for ssh")
                if (":" in self.sshIPAddress):
                    cmIPAddress1,port = self.sshIPAddress.split(":", 1)
                    port = int(port)-2 ## ssh port in lab is usually 2 less than the https port
                    ssh_client.connect(cmIPAddress1,port=port,username=self.sshUserName, password=self.sshPassword)
                else:
                    ssh_client.connect(self.sshIPAddress,username=self.sshUserName, password=self.sshPassword)
            else:
                logger.debug(f"Using sskeys for ssh")
                private_key = paramiko.RSAKey.from_private_key_file(self.sshKeyPath)
                if (":" in self.sshIPAddress):
                    cmIPAddress1,port = self.sshIPAddress.split(":", 1)
                    port = int(port)-2 ## ssh port in lab is usually 2 less than the https port
                    ssh_client.connect(cmIPAddress1,port=port, username=self.sshUserName, pkey=private_key)
                else:
                    ssh_client.connect(self.sshIPAddress, username=self.sshUserName, pkey=private_key)
            return ssh_client
        except Exception as e:
            tb = traceback.format_exc()
            logger.critical(f"An unexpected error occurred: {tb}")
            return None

        
    def run_command_on_host(self,command):
        try: 
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('ascii')
            logger.debug("command : " + command)
            logger.debug("output: " + output)
            lines = output.splitlines()
            return lines
        except Exception as e:
            tb = traceback.format_exc()
            logger.critical(f"An unexpected error occurred: {tb}")
            return None

    def get_object_sub_type(self,objectTypeName):
        method = "POST"
        api_url = "/api/v3/metadata/object_types"
        input_data = {
            "includeChildren": True,
            "names": [
                {
                "fuzzy": True,
                "type": "FUZZABLE_STRING_TYPE_EXACT",
                "value": objectTypeName
                }
            ]
        }
        response_data = self.make_soa_api_call(api_url, method, input_data, insecure=True)
        if response_data is not None:   
            objectTypeDetails = json.loads(response_data.text)
            #logger.debug(f"ObjectTypeDetails: {objectTypeDetails}")
            objectTypeId = objectTypeDetails["objectTypes"][0]["id"]
            pluginName = objectTypeDetails["objectTypes"][0]["plugin"]["objectName"]
            method = "POST"
            api_url = "/api/v3/metadata/object_subtypes"
            input_data = {
                "objectTypeId": objectTypeId,
                "pluginId": pluginName
                }
            response_data_subtypes = self.make_soa_api_call(api_url, method, input_data, insecure=True)
            if response_data_subtypes is not None:   
                subTypeDetails = json.loads(response_data_subtypes.text)
                subTypeList = []
                for subType in subTypeDetails["objectSubtypes"]:
                    subTypeDict= {}
                    subTypeDict["name"] = subType["name"]
                    subTypeDict["common"] = 1 if subType["isCommon"]==True else 0
                    subTypeDict["description"] = subType["description"]
                    subTypeList.append(subTypeDict)
                return subTypeList
            else:
                return None
            
        else:
            return None


    def ingest_dev_obj_ind(self,deviceName,deviceIp_to_be_created,objectList):

        # Check if deviceName exists, if not create the deviceName.

        deviceId, deviceIp = self.get_device_details(deviceIp_to_be_created)
        if deviceId is None:
            logger.debug(f"No device configured for deviceName: {deviceName} ")
            logger.debug(f"Creating new device: {deviceName}, DeviceIP: {deviceIp_to_be_created}")
            deviceId,deviceName = self.create_device(deviceName,deviceIp_to_be_created)
            if deviceId is None:
                    logger.error(f"Failed to create a device with DeviceName: {deviceName}")
                    return 1
        for object in objectList:
            objectName = object["name"]
            objectTypeName = object["type"]
            total_polled_indicator_list = []
            for timestamp in object["timestamps"]:
                polled_indicator_list = timestamp["indicators"]
                total_polled_indicator_list = total_polled_indicator_list + polled_indicator_list
            
           

            # For each indicatorType, verify the indicatorType is present, else create one.

            logger.info(f"Comparing the polled indicator list with indicators created for Device: {deviceName}, Object: {objectName}")
            logger.info(f"Appending any indicators missed during the poll")
            indicator_list=self.create_complete_indicator_list(deviceName,objectName,total_polled_indicator_list)
            # Check if the indicatortypes  in indicatorList are already present in objectType = "SelfMon Last Poll"
            logger.info(f"Getting the list of Indicator Types configured on SevOne for ObjectType: {objectTypeName}")
             # Verify if the objectype is present, else create one.
            indicator_types = self.get_indicator_types(objectTypeName)
            #logger.debug(f"List of IndicatorTypes: {indicator_types}")

            indicator_types_names = {item["name"] for item in indicator_types}

            # Polled indicator Types which are not present in the ObjectType
            indicator_types_to_be_created = [item for item in indicator_list if item["name"] not in indicator_types_names]
            
            names1 = {d['name'] for d in indicator_list}
            names2 = {d['name'] for d in indicator_types}
            logger.debug(f"Object: {objectName}, Indicators Polled: {names1}, ObjectType: {objectTypeName}, Existing IndicatorTypes : {names2}")
            logger.info(f"Comparing the list of IndicatorTypes on ObjectType: {objectTypeName} with the polled list of indicatorTypes.")
            if not(names1.issubset(names2)):
                ## If there are indicators that needs to be ingested, but they are not part of the objectType "SelfMon Last Poll"
                # Update the ObjectType with the list of indicatorTypes
                #Get SubType List
                logger.info(f"Indicator Types found in the polled indicator list, which are not updated on the appliance for the ObjectType: {objectTypeName}")
                logger.info(f"Getting SubTypes of ObjectType: {objectTypeName}")
                subTypeList =self.get_object_sub_type(objectTypeName)
                logger.info(f"Creating ObjectType XML for ObjectType: {objectTypeName} to be ingested to SevOne with complete list of IndicatorTypes")
                object_xml = self.create_object_indicator_type_xml(indicator_list,subTypeList,objectTypeName)
                logger.debug(f"ObjectType XML: {object_xml}")

                # Write the tree to an XML file with the proper declaration
                xmlFileName = f"{objectTypeName}.sevone.xml"
                with open(f"/app/etc/{xmlFileName}", 'w', encoding='utf-8') as f:
                    #f.write('<?xml version="1.0"?>\n')
                    f.write(object_xml)
                logger.info(f"Creating /opt/sevone-uc/ps-di-selfmon/etc/{xmlFileName}")
                logger.info(f"Updating ObjectType: {objectTypeName} by importing XML")
                output = self.run_command_on_host(f"SevOne-cli-import-objecttype-deferred '/opt/sevone-uc/ps-di-selfmon/etc/{xmlFileName}'")


        logger.info(f"Ingesting the polled indicators, deviceName: {deviceName}")
        method = "POST"
        api_url = "/api/v3/devices/data"
        input_data = {
            "automaticCreation": True,
            "distributionOnAllPeers": True,
            "name": deviceName,
            "objects":objectList
        }
        response_data = self.make_soa_api_call(api_url, method, input_data, insecure=True)
        return response_data



    
    
    #Create a list of indicators by appending the missing indicators to the list for that particular device and Objects
    def create_complete_indicator_list(self,deviceName,objectName,input_indicator_list):
        #Get the corresponding peer id
        method = "POST"
        api_url = "/api/v3/metadata/indicators"
        input_data = {
            "deviceObjects": [
                {
                    "deviceName": {
                    "fuzzy": True,
                    "type": "FUZZABLE_STRING_TYPE_EXACT",
                    "value": deviceName
                },
                "objectName": {
                    "fuzzy": True,
                    "type": "FUZZABLE_STRING_TYPE_EXACT",
                    "value": objectName
                }
                }
            ]
        }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        indicator_list = []
        final_indicator_list = []
        if str(response_data.status_code) == "200":    
            indicatorDetails = json.loads(response_data.text)
            if indicatorDetails["indicators"] != []:
                for ind in indicatorDetails["indicators"]:
                    ind_dict = {}
                    ind_dict["name"] = ind["indicatorTypeName"]
                    ind_dict["format"] = ind["format"]
                    indicator_list.append(ind_dict)
            
        final_indicator_list = self.create_super_set_indicator(indicator_list,input_indicator_list)
        return final_indicator_list
    
    
    def create_super_set_indicator(self,object_indicators,polled_indicators):    
        for ind_dict1 in object_indicators:
            indicator_exists_in_polled_indicators = 0
            for ind_dict2 in polled_indicators:
                if ind_dict1["name"] == ind_dict2["name"]:
                    indicator_exists_in_polled_indicators = 1
                    break
            if indicator_exists_in_polled_indicators==0:
                polled_indicators.append(ind_dict1)
        
        return polled_indicators
    
    def get_indicator_types(self,objectType):
        method = "POST"
        api_url = "/api/v3/metadata/indicator_types"
        input_data = {
            "objectTypePaths": [
                {
                "pathComponents": [
                    objectType
                ]
                }
            ]
        }
        response_data= self.make_soa_api_call(api_url, method, input_data, insecure=True)
        if str(response_data.status_code) == "200":
            indicator_type_list = json.loads(response_data.text)
            return indicator_type_list["indicatorTypes"]
        

    def get_object_sub_type(self,objectTypeName):
        method = "POST"
        api_url = "/api/v3/metadata/object_types"
        input_data = {
            "includeChildren": True,
            "names": [
                {
                "fuzzy": True,
                "type": "FUZZABLE_STRING_TYPE_EXACT",
                "value": objectTypeName
                }
            ]
        }
        response_data = self.make_soa_api_call(api_url, method, input_data, insecure=True)
        if str(response_data.status_code) == "200":
            objectTypeDetails = json.loads(response_data.text)
            if objectTypeDetails["objectTypes"] != []: 
                #logger.debug(f"ObjectTypeDetails: {objectTypeDetails}")
                objectTypeId = objectTypeDetails["objectTypes"][0]["id"]
                pluginName = objectTypeDetails["objectTypes"][0]["plugin"]["objectName"]
                method = "POST"
                api_url = "/api/v3/metadata/object_subtypes"
                input_data = {
                    "objectTypeId": objectTypeId,
                    "pluginId": pluginName
                    }
                response_data_subtypes = self.make_soa_api_call(api_url, method, input_data, insecure=True)
                if str(response_data_subtypes.status_code) == "200":
                    subTypeDetails = json.loads(response_data_subtypes.text)
                    subTypeList = []
                    for subType in subTypeDetails["objectSubtypes"]:
                        subTypeDict= {}
                        subTypeDict["name"] = subType["name"]
                        subTypeDict["common"] = 1 if subType["isCommon"]==True else 0
                        subTypeDict["description"] = subType["description"]
                        subTypeList.append(subTypeDict)
                    return subTypeList
                else:
                    return []
            else:
                return []

        else:
            return []
        
    def create_object_indicator_type_xml(self,indicatorList,subTypeList,ObjectType = 'SevOne Appliance'):
        # Create the root element
        root = ET.Element('objectTypes', {'xmlns': 'http://www.sevone.com/xml/2008/plugin.deferred'})
        # Add the objectType element with its sub-elements
        object_type = ET.SubElement(root, 'objectType')
        ET.SubElement(object_type, 'name').text = ObjectType

        sub_types = ET.SubElement(object_type, 'subtypes')
        subTypeNumber = 1  
        for subTypeDict in subTypeList:
            sub_type = ET.SubElement(sub_types, 'subtype')
            ET.SubElement(sub_type, 'number').text = str(subTypeNumber)
            ET.SubElement(sub_type, 'common').text = str(subTypeDict["common"])
            ET.SubElement(sub_type, 'name').text = subTypeDict["name"]
            ET.SubElement(sub_type, 'description').text = subTypeDict["description"]
            subTypeNumber+=1
        # Create the indicatorTypes element
        indicator_types = ET.SubElement(object_type, 'indicatorTypes')

        # Iterate through the data to create the XML structure
        for indicator in indicatorList:
            indicator_type = ET.SubElement(indicator_types, 'indicatorType')
            ET.SubElement(indicator_type, 'name').text = indicator['name']
            ET.SubElement(indicator_type, 'description').text = indicator['name']
            ET.SubElement(indicator_type, 'format').text = indicator['format']
            ET.SubElement(indicator_type, 'hasMaxValue').text = '0'
            try: 
                ET.SubElement(indicator_type, 'dataUnits').text = indicator['units']
            except KeyError:
                logger.info(f"Proceesding without units for IndicatorType: {indicator['name']}")
            ET.SubElement(indicator_type, 'displayUnits').text = ''

        # Create an ElementTree object from the root element
        tree = ET.ElementTree(root)
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')
        #logger.debug(f"ObjectType XML: {tree}")
        parsed_str = minidom.parseString(xml_str)
        pretty_xml_str = parsed_str.toprettyxml(indent="    ")
        return pretty_xml_str
    
                


    def get_and_extract_auth_bearer_token(self):
        # Step 1: Get the authentication token
        url = "https://" + self.IPAddress + "/api/v3/users/signin"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        data = {"password": self.Password, "username": self.UserName}
        
        logger.debug("Url :" + url)
        logger.debug("Getting bearer token for user " + self.UserName)
        res = requests.post(url, headers=headers, json=data, verify=False)
        # Check if the request was successful (status code 200)
        if res.status_code == 200:
            # Parse the JSON data from the response
            response_data = res.json()
            # Extract the token
            token = response_data.get('token')
            if not token:
                logger.error("Error: Authentication token not found in the response.")
                return None
        else:
            # Print an error message if the request was not successful
            logger.error(f"Error: Unable to fetch authentication token. Status code: {res.status_code}")
            return None
    
        return token 
    
    def make_soa_api_call(self,api_url, method, data="",insecure=False):
        try:
            # Set up the headers with the  SOA authentication token
            headers = {
                "Content-Type": "application/json",
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.bearer_token}'
            }
            # Set up the verify parameter based on the 'insecure' flag
            verify = False if insecure else True
            url = "https://" + self.IPAddress + api_url

            logger.info("Making API call")
            logger.info("URL: " + url + ", Method: " + method + ", data: ")
            input_data = json.dumps(data)
            logger.debug(input_data)
            
            # Make the API call with the headers and SSL certificate verification option
            if method == "GET":
                url = url + "?page=0&size=10000"
                response = requests.get(url, headers=headers, verify=verify)
                response_data = response.json()
            elif method == "POST" :
                if input_data == "":
                    response = requests.post(url, headers=headers, verify=verify)
                    response_data = response.json()
                else:
                    response = requests.post(url, headers=headers, verify=verify,data=input_data)
                    response_data = response.json()
            elif method=="PATCH" :
                if input_data == "":
                    response = requests.patch(url, headers=headers, verify=verify)
                else:
                    response = requests.patch(url, headers=headers, verify=verify,data=input_data)
            else:
                logger.error("Unknown http request method passed")
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                logger.info(f"API Call successful")
            else:
                # Print an error message if the request was not successful
                logger.critical(f"Error: Unable to fetch SOA data. Status code: {response.status_code}")
            return response
        except Exception as e:
            # Handle exceptions, such as network errors
            logger.critical(f"An error occurred: {e}")
            return None
        
    

    def create_device(self,deviceName,deviceIP):
        
        ##Create a device   
        logger.debug(f"Creating a device:{deviceName}, deviceIP: {deviceIP},Peer: ClusterMaster")   
        method = "POST"
        api_url = "/api/v3/devices"
        
        #Selfmon devices must always be polled by ClusterMaster hence, PeerID=1
        input_data = {
            "allowDelete": True,
            "altName": deviceName,
            "description": deviceName,
            "ipAddress": deviceIP,
            "name": deviceName,
            "peerId": 1
        }
        response_data_dev_create = self.make_soa_api_call(api_url,method,input_data,insecure=True) 
        if response_data_dev_create is not None:
            if str(response_data_dev_create.status_code) == "409": ## DeviceName already exists, but for a different IP
                logger.info(f"DeviceName: {deviceName} already exists on the cluster")
                deviceName = deviceIP
                logger.info(f"Trying to create device with DeviceName: {deviceName}")
                input_data = {
                    "allowDelete": True,
                    "altName": deviceName,
                    "description": deviceName,
                    "ipAddress": deviceIP,
                    "name": deviceName,
                    "peerId": 1
                }
                response_data_dev_create = self.make_soa_api_call(api_url,method,input_data,insecure=True) 
            deviceIdDetails = json.loads(response_data_dev_create.text)
            deviceId = deviceIdDetails["id"]
            logger.info(f"Device: {deviceName}, deviceID: {deviceId} created.")
        else:
            deviceId = None           
        return deviceId, deviceName

    def get_devices_in_device_group(self,group_path):
        method = "POST"
        api_url = "/api/v3/metadata/devices"
        input_data = {
            "deviceGroupPaths": [
                {
                "pathComponents": [
                    group_path
                ]
                }
            ]
        }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        devices = []    
        if response_data is not None:   
            deviceDetails = json.loads(response_data.text)
            # Uncomment the below to run stub and comment the above line
            # netflowdevicesDetails = response_data        
            for device in deviceDetails["devices"]:
                deviceID = device["id"]
                deviceName = device["name"]
                dict = {"DeviceName": deviceName , "DeviceId": deviceID}
                devices.append(dict)
        else:
            devices = None
        return devices
    
    def get_object_count(self,deviceList):
        for device in deviceList:
            deviceId = device["DeviceId"]
            method = "POST"
            api_url = "/api/v3/metadata/object_count"
            input_data = {                
                    "deviceIds": [
                        deviceId
                    ]
                }
            response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
            objectCount = -1

            if response_data is not None:   
                objectCountDetails = json.loads(response_data.text)
                # Uncomment the below to run stub and comment the above line
                # netflowdevicesDetails = response_data        
                
                objectCount = objectCountDetails["count"]
                device["ObjectCount"] = objectCount
        return deviceList

    def delete_unused_devices(self,deviceList,dryRun):
        deleteDeviceIDList = []
        for device in deviceList:
            deviceId = device["DeviceId"]

            if (device["ObjectCount"]==0):
                deleteDict = {
                        "forceDelete": True,
                        "id": deviceId
                        }
                deleteDeviceIDList.append(deleteDict)
        
        logger.debug("Devices to be deleted : ")
        logger.debug(deleteDeviceIDList)
        if(len(deleteDeviceIDList)>0):
            if(dryRun==0):
                method = "POST"
                api_url = "/api/v3/device/bulk"
                input_data = {
                    "devices": deleteDeviceIDList                   
                }
                response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)

                if response_data is not None:   
                    return response_data
            else:
                logger.debug("DryRun set to 1. Not deleting devices")
        return 0
    
    def get_new_WLC_onboarded(self,metadataNameSpace,metadaAttribute,metadataValue,peer_deviceGroupPathDict):

        #Get list of all WLCs
        method = "POST"
        api_url = "/api/v3/metadata/devices/metadata"
        input_data = {
                "attributeName": {
                    "attribute": metadaAttribute,
                    "namespace": metadataNameSpace
                },
                "value": {
                    "fuzzy": True,
                    "type": "FUZZABLE_STRING_TYPE_REGEX",
                    "value": metadataValue
                }
            }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        list_of_all_WLCs = []

        if response_data is not None:  
            all_wlc_response = json.loads(response_data.text) 
            for wlc_id in all_wlc_response["devices"].keys():
                list_of_all_WLCs.append(wlc_id)
        logger.debug("List of all WLCs:")
        logger.debug(list_of_all_WLCs)
        
        #Get list of onbaorded WLCs
        deviceGroupPathAPIInputDict = {}
        deviceGroupPathAPIInputList = []

        ## Get the list of deviceGroupPaths across all Peers
        deviceGroupPathList = []
        
        for deviceGroupPathsPerPeer in peer_deviceGroupPathDict.values():
            deviceGroupPathsListPerPeer = []
            deviceGroupPathsListPerPeer = list(deviceGroupPathsPerPeer.values())
        deviceGroupPathList = deviceGroupPathList + deviceGroupPathsListPerPeer
        logger.debug("List of all device Group Paths:")
        logger.debug(deviceGroupPathList)

        for deviceGroupPath in deviceGroupPathList:
            deviceGroupPathAPIInputDict = {
                    "pathComponents": [
                        deviceGroupPath
                    ]
                    }
            deviceGroupPathAPIInputList.append(deviceGroupPathAPIInputDict)

        method = "POST"
        api_url = "/api/v3/metadata/devices"
        input_data = { 
                "deviceGroupPaths" : deviceGroupPathAPIInputList
            }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        list_of_onboarded_WLCs = []

        if response_data is not None:   
            onboarded_wlc_response = json.loads(response_data.text) 
            for onboarded_wlc in onboarded_wlc_response["devices"]:
                list_of_onboarded_WLCs.append(onboarded_wlc["id"])
        logger.debug("List of Onboarded WLCs:")
        logger.debug(list_of_onboarded_WLCs)

        set1 = set(list_of_all_WLCs)
        set2 = set(list_of_onboarded_WLCs)

        list_of_new_WLCs = list(set1 - set2)

        return list_of_new_WLCs
    
    def get_device_details(self,deviceIP):
        method = "POST"
        api_url = "/api/v3/metadata/devices"
        input_data = {
            "ip": {
                "fuzzy": True,
                "type": "FUZZABLE_STRING_TYPE_EXACT",
                "value": deviceIP
            }
        }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        
        if response_data is not None:   
            deviceDetails = json.loads(response_data.text) 
            if len(deviceDetails["devices"])==0:
                logger.debug(f"No Device configured for DeviceIP: {deviceIP}")
                deviceName = None
                deviceId = None
            else:
                deviceName = deviceDetails["devices"][0]["name"]
                deviceId = deviceDetails["devices"][0]["id"]
        
        return deviceName, deviceId
    
    def get_device_metadata_details(self,metadataNameSpace,metadaAttribute,deviceIdList):
        #Get list of all WLCs
        method = "POST"
        api_url = "/api/v3/metadata/devices/metadata"
        input_data = {
                "attributeName": {
                    "attribute": metadaAttribute,
                    "namespace": metadataNameSpace
                },
                "entityIds": deviceIdList
            }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        list_device_metadata_details = []

        if response_data is not None:  
            metadata_response = json.loads(response_data.text) 
            for deviceId in deviceIdList:
                metadataDetailsDict = {}
                metadataDetailsDict["DeviceId"] = deviceId
                metadataDetailsDict["Metadata Attribute"] = metadaAttribute
                metadataDetailsDict["Metadata Value"] = list(list(list(metadata_response["devices"][deviceId]["namespaces"].values())[0]["attributes"].values())[0]["values"].values())[0]
                list_device_metadata_details.append(metadataDetailsDict)
        return list_device_metadata_details
    
