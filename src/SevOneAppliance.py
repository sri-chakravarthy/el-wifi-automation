import requests
from logger_config import logger
from PasswordEncryption import *
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



class SevOneAppliance: 
    def __init__(self,ipAddress,username,password):
        self.IPAddress = ipAddress
        self.UserName = username
        self.Password = password
        self.bearer_token = self.get_and_extract_auth_bearer_token()

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

            logger.debug("Making API call")
            logger.debug("URL: " + url + ", Method: " + method + ", data: ")
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
                logger.debug("Unknown http request method passed")
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                logger.debug(f"API Call successful")
            else:
                # Print an error message if the request was not successful
                logger.error(f"Error: Unable to fetch SOA data. Status code: {response.status_code}")
            return response
        except Exception as e:
            # Handle exceptions, such as network errors
            logger.error(f"An error occurred: {e}")
            return None
        
    def get_device_group_id(self,group_path):
        method = "POST"
        api_url = "/api/v3/metadata/device_groups"
        input_data = {
            "paths": [
                {
                "pathComponents": [
                    group_path
                ]
                }
            ]
        }

        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        device_groups = []    
        if response_data is not None:   
            deviceGroupDetails = json.loads(response_data.text)
            # Uncomment the below to run stub and comment the above line
            # netflowdevicesDetails = response_data        
            for deviceGroup in deviceGroupDetails["groups"]:
                deviceGroupID = deviceGroup["id"]
                deviceGroupChildren = deviceGroup["children"]
                dict = {"DeviceGroupPath": group_path , "id": deviceGroupID}
                device_groups.append(dict)
        else:
            device_groups = None
        return device_groups

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
    
    def get_device_details(self,deviceIdList):
        method = "POST"
        api_url = "/api/v3/metadata/devices/metadata"
        input_data = {
                "attributeName": {
                "attribute": "sysDescr",
                "namespace": "SevOne"
            },
            "entityIds": deviceIdList
        }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        list_wlc_device_details = []
        if response_data is not None:   
            wlc_details_response = json.loads(response_data.text) 
            for deviceId in deviceIdList:
                deviceDetailsDict = {}
                deviceDetailsDict["DeviceId"] = deviceId
                deviceDetailsDict["DeviceName"] = wlc_details_response["devices"][deviceId]["name"]
                deviceDetailsDict["DeviceVendor"] = list(list(list(wlc_details_response["devices"][deviceId]["namespaces"].values())[0]["attributes"].values())[0]["values"].values())[0]
                deviceDetailsDict["DeviceIP"] = wlc_details_response["devices"][deviceId]["device"]["ip"]
                list_wlc_device_details.append(deviceDetailsDict)
        return list_wlc_device_details 
    
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
    

    def get_wlc_access_point_count(self,wlcDetailsList,CiscoAPCountOID,ArubaAPCountOID):
        
        #Get Cisco and Aruba DeviceId lists
        #cisco_wlc_id_list=[]
        #aruba_wlc_id_list=[]
        cisco_input_data_list = []
        aruba_input_data_list = []
        for wlc in wlcDetailsList:
            ciscoRegExMatch = re.search('Cisco',wlc["DeviceVendor"],re.IGNORECASE)
            if ciscoRegExMatch:
                deviceDict = {            
                "deviceId": wlc["DeviceId"],
                "oids": [
                    CiscoAPCountOID
                ]
                }
                cisco_input_data_list.append(deviceDict)

            arubaRegMatch = re.search('aruba',wlc["DeviceVendor"],re.IGNORECASE)
            if arubaRegMatch:
                deviceDict = {            
                "deviceId": wlc["DeviceId"],
                "oids": [
                    ArubaAPCountOID
                ]
                }
                aruba_input_data_list.append(deviceDict)
    
        
        # Get the number of APs for all the WLCs
               
        method = "POST"
        api_url = "/api/v3/metadata/devices/snmpwalk"
        input_data = {
            "devices": cisco_input_data_list + aruba_input_data_list
        }
        #logger.debug("SNMP Walk API input:")
        #logger.debug(input_data)
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        wlc_ap_count_list = []
        
        if response_data is not None:   
            snmp_walk_response = json.loads(response_data.text) 
            #logger.debug("SNMP Walk response:")
            #logger.debug(response_data)
            for wlc in snmp_walk_response["devices"]:
                wlc_ap_count_dict = {}
                ap_count = 0
                wlc_ap_count_dict["DeviceId"] = wlc["deviceId"]
                ap_list =  wlc["snmpWalk"][0]["outputLines"]
                ap_count = len(ap_list)

                #Check if there was an error in snmp walk and the list doesnt contain the actual AP
                if (ap_count == 1):
                    ap_text = re.search("Hex-STRING",ap_list[0],re.IGNORECASE)
                    if ap_text is None:
                        ap_count = -1

                wlc_ap_count_dict["AP_Count"] = ap_count
                wlc_ap_count_list.append(wlc_ap_count_dict)

        #logger.debug("APCount list:")
        #logger.debug(wlc_ap_count_list)

        
        # Add the APCount Key value pair to the original Device Details List by merging the two
         #Create a dictionary to store deviceID-location mapping
        device_apcount_map = {d['DeviceId']: d['AP_Count'] for d in wlc_ap_count_list}
        # Iterate through each dictionary in list1
        for d in wlcDetailsList:
            # Check if the deviceID exists in the device_location_map
            if d['DeviceId'] in device_apcount_map:
                # Update the dictionary in list1 with the location from list2
                d.update({'AP_Count': device_apcount_map[d['DeviceId']]})
        
        return wlcDetailsList


    def get_peer_capacity(self,peer_deviceGroupPathList):
        api_input_peer_list = []
        for peer in peer_deviceGroupPathList.keys():
            inputDict = {
                "fuzzy": True,
                "type": "FUZZABLE_STRING_TYPE_EXACT",
                "value": peer
            }
            api_input_peer_list.append(inputDict)
        method = "POST"
        api_url = "/api/v3/peers"
        input_data = {
            "names": api_input_peer_list 
        }

        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        peer_capacity_list = []
        if response_data is not None:   
            peer_response = json.loads(response_data.text) 
            
            for peer in peer_response["peers"]:
                peer_dict = {}
                peer_dict["Id"] = peer["id"]
                peer_dict["Name"] = peer["name"]
                peer_dict["IP"] = peer["ip"]
                obj_available = int(peer["capacity"]) - int(peer["totalLoad"])
                peer_dict["Objects Available"] = obj_available
                peer_dict["Obj Util Percent"] = (int(peer["totalLoad"])/int(peer["capacity"]))*100
                peer_capacity_list.append(peer_dict)
        
        return peer_capacity_list
    
    def pin_device_to_device_group(self,deviceId,deviceGroupPath):
        # Get the device group name
        deviceGroupHeirarchy = deviceGroupPath.split("/")
        deviceGroupName = deviceGroupHeirarchy[len(deviceGroupHeirarchy)-1]
        
        #Get the device Group ID.
        method = "POST"
        api_url = "/api/v3/devicegroups/filter"
        input_data = {
            "name": deviceGroupName
            }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        deviceGroupId = None
        if response_data is not None:   
            groupIdResponse = json.loads(response_data.text) 
            for deviceGroup in groupIdResponse["content"]:
                if deviceGroup["name"]==deviceGroupName:
                    deviceGroupId = deviceGroup["id"]
        
        ## Pin the device to the deviceGroup
        if deviceGroupId is not None:
            method = "POST"
            api_url = "/api/v3/devicegroups/" + deviceGroupId + "/members/" + deviceId
            response_data = self.make_soa_api_call(api_url,method,insecure=True)
            if response_data.status_code == 200:   
                logger.debug("The DeviceId: " + deviceId + " has been successfully pinned to the deviceGroupPath: " + deviceGroupPath )
            else:
                logger.debug("The pinning of DeviceId: " + deviceId + " to the deviceGroupPath: " + deviceGroupPath + " is unsuccessful. Error code: " + response_data.status_code)
                return 1
        else:
            logger.debug(" Could not find deviceGroupID for the Device Group Path: " + deviceGroupPath)
            return 1
        return 0
        
    def update_peer_polling_for_device(self,deviceId,peerId):
        method = "POST"
        api_url = "/api/v3/devices/edit"
        input_data = {
            "commit": True,
            "device": {
                "config": {
                "peerId": peerId
                }
            },
            "deviceId": deviceId
        }
        response_data = self.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data.status_code == 200:   
            logger.debug("The DeviceId: " + deviceId + " has been successfully updated to be polled by peerId: " + peerId )
        else:
            logger.debug("The update of DeviceId: " + deviceId + " is unsuccessful. Error code: " + response_data.status_code)
            return 1
        return 0
        

            


    def send_email(self,smtpServer,smtpPort,recepientEmailList,senderEmailIAddress,senderEmailPassword,subject,emailBody):

        # Create a multipart message
        message = MIMEMultipart()
        message["From"] = senderEmailIAddress
        message["To"] = recepientEmailList
        message["Subject"] = subject

        # Add body to email
        
        message.attach(MIMEText(emailBody, "plain"))

        # Connect to the SMTP server
        with smtplib.SMTP(smtpServer, smtpPort) as server:  # Replace smtp.example.com with your SMTP server
            server.starttls()  # Enable TLS encryption
            server.login(senderEmailIAddress, senderEmailPassword)
            text = message.as_string()
            server.sendmail(senderEmailIAddress, recepientEmailList, text)
            print("Email sent successfully!")
            return 0
        


