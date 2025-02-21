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

class WifiAutomations:

    def parse_groups(self,data):
        result = {}
        
        def traverse(children):
            for child in children:
                result[child["id"]] = {
                    "NoofDevices": None,
                    "DeviceGroupPath": child["path"]
                }
                if "children" in child and child["children"]:
                    traverse(child["children"])
        
        if "groups" in data:
            traverse(data["groups"])
        
        return result




    def AP_Availability_Count(self,SevOne_appliance_obj,automationDict):
        logger.info(f"Starting automation: {automationDict['Name']} ")
        parentDeviceGroupPath=automationDict['ParentDeviceGroup']
        logger.info(f"AP Device Group to check: {automationDict['ParentDeviceGroup']}")

        # Getting all sub device groups and devices in each device group
        device_groups = self.get_all_device_groups(SevOne_appliance_obj,parentDeviceGroupPath)
        logger.debug(f"Device Groups: {device_groups}")

        # Create a dictionary as below
        #  {
        #       <deviceGroupName>:{
        #               "NoofDevices:<Value>,
        #               "DeviceGroupID": <value>,
        #               
        #               }
        #  }
        deviceGroupDict = self.parse_groups(device_groups)

        # Get LastDataPoint of all devices under the parent device group using API call
   
       
        logger.info(f"Device Groups discovered: {deviceGroupDict}")
        deviceGroupIdList = list(deviceGroupDict.keys())
        logger.info(f"Device Group Id list: {deviceGroupIdList}")
        availability_status = self.get_device_availability(SevOne_appliance_obj,deviceGroupIdList)
        logger.debug(f"availability_status: {availability_status}")

        # Count the number of APs in each device group and  additional Key value pairs into the dictionary - deviceGroupDict
        #               
        # Keys : NoofDevices, Available, NotAvailable
        # Initialize counts
        for group_id in deviceGroupDict:
            deviceGroupDict[group_id]["NoofDevices"] = 0
            deviceGroupDict[group_id]["Available"] = 0
            deviceGroupDict[group_id]["Unavailable"] = 0

        # Process the IndDictionary
        for indicator in availability_status["indicatorResults"]:
            device_groups = indicator["deviceGroups"]
            availability = indicator["dataPoint"]["value"]
            
            for group_id in device_groups:
                if group_id in deviceGroupDict:
                    deviceGroupDict[group_id]["NoofDevices"] += 1
                    if availability == 100:
                        deviceGroupDict[group_id]["Available"] += 1
                    else:
                        deviceGroupDict[group_id]["Unavailable"] += 1

        logger.info(f"DeviceGroupDict after availability check: {json.dumps(deviceGroupDict, indent=4)}")

        # Format the Information into Device - Object - indicator
        # Device - "Device-Availaibity-Count"
        # Objects - <DeviceGroupPath> - Remove 'All Device Group from the Path
        # Indicator - NoofDevices, Available, Unavailable

        objectList = []
        timestamp = int(time.time())
        for group_id in deviceGroupDict:
            ShortDevGroupPath = "/".join(deviceGroupDict[group_id]["DeviceGroupPath"].split("/")[2:])
            objectDict = {
                "automaticCreation": True,
                "description": "Group members Count Metrics",
                "name": ShortDevGroupPath,
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "name": "No of Devices",
                        "units": "Number",
                        "value": deviceGroupDict[group_id]["NoofDevices"]
                        },
                        {
                        "format": "GAUGE",
                        "name": "Available",
                        "units": "Number",
                        "value": deviceGroupDict[group_id]["Available"]
                        },
                        {
                        "format": "GAUGE",
                        "name": "UnAvailable",
                        "units": "Number",
                        "value": deviceGroupDict[group_id]["Unavailable"]
                        }
                    ],
                    "timestamp": timestamp
                    }
                ],
                    "type": "AP Group Counts"
                }
            if objectDict["name"] != "":
                objectList.append(objectDict)
        logger.info(f"ObjectList: {json.dumps(objectList, indent=4)}")
        result = SevOne_appliance_obj.ingest_dev_obj_ind("AP-Group-Count", "5.5.5.5",objectList)

        # Get no of devices under each device group.
        if result==1:
            logger.error(f"Error ingesting data into SevOne.")
        else:
            logger.debug(f"Result of ingestion: {result}")
    

        '''
        ind_object_list = [
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "AP_agg",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 10
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 9
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 1
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                }
            ]
        chn_object_list = [
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "AP_agg",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 0
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                }
            ]
        ban_object_list = [
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "AP_agg",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 4
                        },
                        {
                        "format": "GAUGE",
                        "maxValue": 0,
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 1
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                }
            ]
        
        all_obj_list = [
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "IND",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 10
                        },
                        {
                        "format": "GAUGE",
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 9
                        },
                        {
                        "format": "GAUGE",
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 1
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                },
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "CHN",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 0
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                },
                {
                "automaticCreation": True,
                "description": "Aggregated metrics",
                "name": "BAN",
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": [
                        {
                        "format": "GAUGE",
                        "name": "Total AP Count",
                        "units": "Number",
                        "value": 5
                        },
                        {
                        "format": "GAUGE",
                        "name": "Available AP Count",
                        "units": "Number",
                        "value": 4
                        },
                        {
                        "format": "GAUGE",
                        "name": "UnAvailable AP Count",
                        "units": "Number",
                        "value": 1
                        }
                    ],
                    "timestamp": "1740044218"
                    }
                ],
                    "type": "AP Group Aggregation"
                }
            ]
   
        result = SevOne_appliance_obj.ingest_dev_obj_ind("IND", "1.1.1.1",ind_object_list)
        result = SevOne_appliance_obj.ingest_dev_obj_ind("CHN", "2.2.2.2",chn_object_list)
        result = SevOne_appliance_obj.ingest_dev_obj_ind("BAN", "3.3.3.3",ban_object_list)
        result = SevOne_appliance_obj.ingest_dev_obj_ind("APCount", "4.4.4.4",all_obj_list)

        # Get no of devices under each device group.
        if result==1:
            logger.error(f"Error ingesting data into SevOne.")
        else:
            logger.debug(f"Result of ingestion: {result}")
        '''

        


    def get_all_device_groups(self,SevOne_appliance_obj,parentDeviceGroupPath):
        #Create the indicatorType
        method = "POST"
        api_url = "/api/v3/metadata/device_groups"
        input_data = {
            "paths": [
                {
                "pathComponents": [
                    parentDeviceGroupPath
                ]
                }
            ]
        }
        response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data is not None:
            deviceGroups = json.loads(response_data.text)
            return deviceGroups
        else:
            return None
        
    
    def get_device_availability(self,SevOne_appliance_obj,deviceGroupIdList):
        #Create the indicatorType
        method = "POST"
        api_url = "/api/v3/data/last_data_point"
        input_data = { 
            "indicatorFilters": [
                {

                "deviceTagIds": deviceGroupIdList ,

                "indicatorTypeNames": [
                    {
                    "fuzzy": True,
                    "type": "FUZZABLE_STRING_TYPE_EXACT",
                    "value": "availability"
                    }
                ],

                "objectTypePaths": [
                    {
                    "pathComponents": [
                        "Wifi Access Point"
                    ]
                    }
                ],
                "pluginIds": [
                    "10"
                ]
                }
            ]
        }
        response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data is not None:
            lastDataPoint = json.loads(response_data.text)
            return lastDataPoint
        else:
            return None
