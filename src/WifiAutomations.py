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

    def parse_groups(self,data,result={}):
        #result = {}
        
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




    def Automation(self,SevOne_appliance_obj,automationDict):
        logger.info(f"Starting automation: {automationDict['Name']} ")
        if (automationDict['Name'] == 'WLC-Group-Count' or automationDict['Name'] == 'AP-Group-Count'):
            self.group_count(SevOne_appliance_obj,automationDict)
        elif (automationDict['Name'] == 'Region-Station-Count'):
            self.station_count(SevOne_appliance_obj,automationDict)
        elif (automationDict['Name'] == 'Update-WLC-AP-Metadata'):
            self.update_wlc_metadata(SevOne_appliance_obj,automationDict)
        elif (automationDict['Name'] == 'Alerts-AP-Count'):
            self.alerts_ap_count(SevOne_appliance_obj,automationDict)
        elif (automationDict['Name'] == 'Severity-AP-Count'):
            self.severity_ap_count(SevOne_appliance_obj,automationDict)

    def severity_ap_count(self,SevOne_appliance_obj,automationDict):
        deviceGroupDict = {}
        for parentDeviceGroupPath in automationDict['ParentDeviceGroup']:
            #parentDeviceGroupPath=automationDict['ParentDeviceGroup']
            logger.info(f"Device Group to check: {parentDeviceGroupPath}")

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
            deviceGroupDict = self.parse_groups(device_groups,deviceGroupDict)

            # Get LastDataPoint of all devices under the parent device group using API call       
            logger.info(f"Device Groups discovered: {deviceGroupDict}")

        deviceGroupIdList = list(deviceGroupDict.keys())
        logger.info(f"Device Group Id list: {deviceGroupIdList}")

        deviceGroupDict = self.get_device_count(SevOne_appliance_obj,deviceGroupDict)

        '''
        #get plugin Id
        pluginId = SevOne_appliance_obj.get_plugin_id(automationDict["Plugin"])
        availability_status = self.get_device_availability(SevOne_appliance_obj,deviceGroupIdList,automationDict["objectTypePath"],automationDict["indicatorName"],pluginId)
        logger.debug(f"availability_status: {availability_status}")

        # Count the number of APs in each device group and  additional Key value pairs into the dictionary - deviceGroupDict
        #               
        # Keys : NoofDevices, Available, NotAvailable
        # Initialize counts
        for group_id in deviceGroupDict:
            deviceGroupDict[group_id]["NoofDevices"] = 0

        # Process the IndDictionary
        for indicator in availability_status["indicatorResults"]:
            if indicator["deviceName"] not in  automationDict["DevicesToExclude"]:
                device_groups = indicator["deviceGroups"]
            
                for group_id in device_groups:
                    if group_id in deviceGroupDict :
                        deviceGroupDict[group_id]["NoofDevices"] += 1
        '''
        timestamp = int(time.time())
        if automationDict["AlertMonitoringStartTime"] == 0:
            startTime = 0

        endTime = timestamp
        
        
        
        #logger.info(f"DeviceGroupDict after availability check: {json.dumps(deviceGroupDict, indent=4)}")
        for deviceGroupId in deviceGroupIdList:
            severityDeviceIDDict = self.get_device_count_with_alerts_severity(SevOne_appliance_obj,deviceGroupId,automationDict["AlertSeverityDict"],startTime,endTime)
            logger.debug(f"DeviceGroup: {deviceGroupId}, severityDeviceIDDict:{severityDeviceIDDict}")
            if severityDeviceIDDict is not None:
                for severity,deviceSet in severityDeviceIDDict.items():
                    count_of_devices_with_alerts = len(deviceSet)
                    deviceGroupDict[deviceGroupId][severity] = count_of_devices_with_alerts
            else:
                logger.error("Problem getting the device count with Alerts. Check logs")
        logger.info(f"DeviceGroupDict after alert count check: {json.dumps(deviceGroupDict, indent=4)}")

        # Format the Information into Device - Object - indicator
        # Device - "Device-Availaibity-Count"
        # Objects - <DeviceGroupPath> - Remove 'All Device Group from the Path
        # Indicator - No of Devices, No of Devices with Alerts
        
        objectList = []
        indicatorList = []
        
        for group_id in deviceGroupDict.keys():
            ShortDevGroupPath = "/".join(deviceGroupDict[group_id]["DeviceGroupPath"].split("/")[2:])
            indicatorList = []
            for key,value in deviceGroupDict[group_id].items():
                logger.debug(f"Key: {key}, Value:{value}")
                if key != "NoofDevices" and key != "DeviceGroupPath": 
                    indDict = {
                        "format": "GAUGE",
                        "name": key + " Devices",
                        "units": "Number",
                        "value": value
                    }
                    indicatorList.append(indDict)
            indicatorList.append({
                "format": "GAUGE",
                "name": "No of Devices",
                "units": "Number",
                "value": deviceGroupDict[group_id]["NoofDevices"]
            })
            objectDict = {
                "automaticCreation": True,
                "description": "Group members Count Metrics",
                "name": ShortDevGroupPath,
                "pluginName": "DEFERRED",
                "timestamps": [
                    {
                    "indicators": indicatorList,
                    "timestamp": timestamp
                    }
                ],
                    "type": "Device Group Counts"
                }
            if objectDict["name"] != "":
                objectList.append(objectDict)
        logger.info(f"ObjectList: {json.dumps(objectList, indent=4)}")
        result = SevOne_appliance_obj.ingest_dev_obj_ind(automationDict["Name"],automationDict["IPToBeCreated"],objectList)
        automationDict["AlertMonitoringStartTime"] = endTime

        # Get no of devices under each device group.
        if result==1:
            logger.error(f"Error ingesting data into SevOne.")
        else:
            logger.debug(f"Result of ingestion: {result}")
        
    def get_device_count(self,SevOne_appliance_obj,deviceGroupDict):
        '''
         {'201': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP'}, '202': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND'}, '203': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/BAN'}, '206': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/BAN/SA'}, '207': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/BAN/EGL'}, '204': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/CHN'}, '208': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/CHN/SIR'}, '209': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/CHN/AMB'}, '205': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/HYD'}, '210': {'NoofDevices': None, 'DeviceGroupPath': 'All Device Groups/AP/IND/HYD/MAD'}}
        '''
        
        for deviceGroupId in deviceGroupDict.keys():
            method = "POST"
            api_url = "/api/v3/metadata/device_count"
            input_data = {
                "deviceGroupIds": [
                    deviceGroupId
                ]
            }
            response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
            if response_data.status_code == 200:
                count = json.loads(response_data.text)
                deviceGroupDict[deviceGroupId]["NoofDevices"] = count["count"]
        
        return deviceGroupDict


    def alerts_ap_count(self,SevOne_appliance_obj,automationDict):
        parentDeviceGroupPath=automationDict['ParentDeviceGroup']
        logger.info(f"Device Group to check: {automationDict['ParentDeviceGroup']}")

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

        #get plugin Id
        pluginId = SevOne_appliance_obj.get_plugin_id(automationDict["Plugin"])
        availability_status = self.get_device_availability(SevOne_appliance_obj,deviceGroupIdList,automationDict["objectTypePath"],automationDict["indicatorName"],pluginId)
        logger.debug(f"availability_status: {availability_status}")

        # Count the number of APs in each device group and  additional Key value pairs into the dictionary - deviceGroupDict
        #               
        # Keys : NoofDevices, Available, NotAvailable
        # Initialize counts
        for group_id in deviceGroupDict:
            deviceGroupDict[group_id]["NoofDevices"] = 0

        # Process the IndDictionary
        for indicator in availability_status["indicatorResults"]:
            if indicator["deviceName"] not in  automationDict["DevicesToExclude"]:
                device_groups = indicator["deviceGroups"]
            
                for group_id in device_groups:
                    if group_id in deviceGroupDict :
                        deviceGroupDict[group_id]["NoofDevices"] += 1
        timestamp = int(time.time())
        if automationDict["AlertMonitoringStartTime"] == 0:
            startTime = 0

        endTime = timestamp
        
        
        
        #logger.info(f"DeviceGroupDict after availability check: {json.dumps(deviceGroupDict, indent=4)}")
        for deviceGroupId in deviceGroupIdList:
            deviceSet = self.get_device_count_with_alerts(SevOne_appliance_obj,deviceGroupId,automationDict["AlertPolicyIdList"],startTime,endTime)
            if deviceSet is not None:
                count_of_devices_with_alerts = len(deviceSet)
                deviceGroupDict[deviceGroupId]["NoOfDevicesWithAlerts"] = count_of_devices_with_alerts
            else:
                logger.error("Problem getting the device count with Alerts. Check logs")
        logger.info(f"DeviceGroupDict after alert count check: {json.dumps(deviceGroupDict, indent=4)}")

        # Format the Information into Device - Object - indicator
        # Device - "Device-Availaibity-Count"
        # Objects - <DeviceGroupPath> - Remove 'All Device Group from the Path
        # Indicator - No of Devices, No of Devices with Alerts

        objectList = []
        
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
                        "name": "No of Devices with Alerts",
                        "units": "Number",
                        "value": deviceGroupDict[group_id]["NoOfDevicesWithAlerts"]
                        }
                    ],
                    "timestamp": timestamp
                    }
                ],
                    "type": "Device Group Counts"
                }
            if objectDict["name"] != "":
                objectList.append(objectDict)
        logger.info(f"ObjectList: {json.dumps(objectList, indent=4)}")
        result = SevOne_appliance_obj.ingest_dev_obj_ind(automationDict["Name"],automationDict["IPToBeCreated"],objectList)
        automationDict["AlertMonitoringStartTime"] = endTime

        # Get no of devices under each device group.
        if result==1:
            logger.error(f"Error ingesting data into SevOne.")
        else:
            logger.debug(f"Result of ingestion: {result}")


    
    def update_wlc_metadata(self,SevOne_appliance_obj,automationDict):
        parentDeviceGroupPath=automationDict['ParentDeviceGroup']
        logger.info(f"Device Group to check: {automationDict['ParentDeviceGroup']}")

        # Getting all sub device groups and devices in each device group
        device_groups = self.get_all_device_groups(SevOne_appliance_obj,parentDeviceGroupPath)
        logger.debug(f"Device Groups: {device_groups}")

        #For each of the above device groups, get all devices
        wlc_deviceGroups = device_groups["groups"][0]["children"]
        wlc_deviceGroupNames = [device["name"] for device in wlc_deviceGroups]
        logger.debug(f" WLC Device group Names : {wlc_deviceGroupNames}")

        # For each of the WLC listed, get all APs associated [ List of devices under that group ] and their device IDs
        for wlc in wlc_deviceGroups:
            wlcName = wlc["name"]
            deviceIdList = self.get_all_devices_under_device_group(SevOne_appliance_obj,wlc["path"])
            logger.debug(f" DeviceIdList for {wlcName} : {deviceIdList}")

    def get_device_count_with_alerts(self,SevOne_appliance_obj,deviceGroupId,policyIdList,startTime,endTime):
        policyFilterList = []
        for policyId in policyIdList:
            policyDict = {
                "policyId": {
                    "value": policyId
                } 
            }
            policyFilterList.append(policyDict)
        
        method = "POST"
        api_url = "/api/v3/alerts"
        input_data = {  
            "query": {
                "alertStatus": "OPEN",
                "deviceGroups": {
                "ids": [deviceGroupId]
                },
                
                "filters": policyFilterList,
                "showIgnored": True,
                "timeRange": {
                "specificInterval": {
                    "endTime": endTime,
                    "startTime": startTime
                }
                }
            }
            }
        response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data.status_code == 200  :
            alertList = json.loads(response_data.text)
            deviceIdSet = set()
            for alert in alertList["alerts"]:
                deviceIdSet.add(alert["device"]["id"])
            return deviceIdSet
        else:
            return None

    def get_device_count_with_alerts_severity(self,SevOne_appliance_obj,deviceGroupId,alert_severity_dict,startTime,endTime):
        
        method = "POST"
        api_url = "/api/v3/alerts"
        input_data = {  
            "query": {
                "alertStatus": "OPEN",
                "deviceGroups": {
                "ids": [deviceGroupId]
                },

                "showIgnored": True,
                "timeRange": {
                "specificInterval": {
                    "endTime": endTime,
                    "startTime": startTime
                }
                }
            }
            }
        response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data.status_code == 200 :
            alertList = json.loads(response_data.text)
            logger.debug(f"AlertList for DeviceGroupID {deviceGroupId} : {alertList}")

            #Initialize a dictionary, with Severity values as key and a set with deviceIds as value
            severityDeviceCountDict = {}
            for severity in alert_severity_dict.keys():
                severityDeviceCountDict[severity] = set()

            if alertList["alerts"] != []:
                for alert in alertList["alerts"]:
                    if "id" in alert["device"]:
                        severityDeviceCountDict[alert["severity"]].add(alert["device"]["id"])
                        logger.debug(f"Added device to  severityDeviceCountDict: {severityDeviceCountDict}")
                # Check if there are repeats of DeviceId under different Severities. Keep it for the highest Severity
                procSeverityDeviceCountDict = self.deduplicate_device_ids_by_severity(severityDeviceCountDict)
                logger.debug(f"procSeverityDeviceCountDict: {procSeverityDeviceCountDict}")

                return procSeverityDeviceCountDict
            else:
                return severityDeviceCountDict

        else:
            return None
    
    def deduplicate_device_ids_by_severity(self,alert_dict):
        # Define severity levels from least to most severe
        severity_order = [
            'CLEAR', 'DEBUG', 'INFO', 'NOTICE', 'WARNING', 'ERROR',
            'CRITICAL', 'ALERT', 'EMERGENCY'
        ]

        # Create a set to track device IDs already seen at higher severities
        seen_devices = set()

        # Traverse from highest to lowest severity
        for severity in reversed(severity_order):
            devices = alert_dict.get(severity, set())
            # Remove devices already seen in higher severities
            alert_dict[severity] = devices - seen_devices
            # Add current devices to seen
            seen_devices.update(alert_dict[severity])

        return alert_dict
        
    def get_all_devices_under_device_group(self,SevOne_appliance_obj,deviceGroupPath):
        method = "POST"
        api_url = "/api/v3/data/last_data_point"
        input_data = {
        "deviceGroupPaths": [
                {
                    "pathComponents": [
                        deviceGroupPath
                    ]
                }
            ]
        }
        response_data = SevOne_appliance_obj.make_soa_api_call(api_url,method,input_data,insecure=True)
        if response_data is not None:
            deviceList = json.loads(response_data.text)
            deviceIdList= [device["id"] for device in deviceList["devices"]]
            return deviceIdList
        else:
            return None
    
    def station_count(self,SevOne_appliance_obj,automationDict):
        parentDeviceGroupPath=automationDict['ParentDeviceGroup']
        logger.info(f"Device Group to check: {automationDict['ParentDeviceGroup']}")

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

        #get plugin Id
        pluginId = SevOne_appliance_obj.get_plugin_id(automationDict["Plugin"])
        group_station_count = self.get_group_station_count(SevOne_appliance_obj,deviceGroupIdList,automationDict["objectTypePath"],automationDict["indicatorName"],pluginId)
        logger.debug(f"group_station_count: {group_station_count}")

        # Get the count of No of Stations in each device group and additional Key value pairs into the dictionary - deviceGroupDict
        #               
        # Keys : NoOfStations
        # Initialize counts
        for group_id in deviceGroupDict:
            deviceGroupDict[group_id]["NoOfStations"] = 0

        # Process the IndDictionary
        for indicator in group_station_count["indicatorResults"]:
            device_groups = indicator["deviceGroups"]
            stationCount = indicator["dataPoint"]["value"]
            
            for group_id in device_groups:
                if group_id in deviceGroupDict:
                    deviceGroupDict[group_id]["NoOfStations"] += stationCount
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
                        "name": "No of Stations",
                        "units": "Number",
                        "value": deviceGroupDict[group_id]["NoOfStations"]
                        }
                    ],
                    "timestamp": timestamp
                    }
                ],
                    "type": "Device Group Counts"
                }
            if objectDict["name"] != "":
                objectList.append(objectDict)
        logger.info(f"ObjectList: {json.dumps(objectList, indent=4)}")
        result = SevOne_appliance_obj.ingest_dev_obj_ind(automationDict["Name"],automationDict["IPToBeCreated"],objectList)

        # Get no of devices under each device group.
        if result==1:
            logger.error(f"Error ingesting data into SevOne.")
        else:
            logger.debug(f"Result of ingestion: {result}")

    
    def get_group_station_count(self,SevOne_appliance_obj,deviceGroupIdList,objectTypeName,indicatorTypeName,pluginId):
        #Create the indicatorType
        method = "POST"
        api_url = "/api/v3/data/last_data_point"
        input_data = { 
            "indicatorFilters": [
                {

                "deviceTagIds": deviceGroupIdList ,

                "indicatorTypeNames": [
                    {
                    "fuzzy": False,
                    "type": "FUZZABLE_STRING_TYPE_EXACT",
                    "value": indicatorTypeName
                    }
                ],

                "objectTypePaths": [
                    {
                    "pathComponents": [
                        objectTypeName
                    ]
                    }
                ],
                "pluginIds": [
                    pluginId
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
    
        
    
    def group_count(self,SevOne_appliance_obj,automationDict):
        parentDeviceGroupPath=automationDict['ParentDeviceGroup']
        logger.info(f"Device Group to check: {automationDict['ParentDeviceGroup']}")

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

        #get plugin Id
        pluginId = SevOne_appliance_obj.get_plugin_id(automationDict["Plugin"])
        availability_status = self.get_device_availability(SevOne_appliance_obj,deviceGroupIdList,automationDict["objectTypePath"],automationDict["indicatorName"],pluginId)
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
                    "type": "Device Group Counts"
                }
            if objectDict["name"] != "":
                objectList.append(objectDict)
        logger.info(f"ObjectList: {json.dumps(objectList, indent=4)}")
        result = SevOne_appliance_obj.ingest_dev_obj_ind(automationDict["Name"],automationDict["IPToBeCreated"],objectList)

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
        
    
    def get_device_availability(self,SevOne_appliance_obj,deviceGroupIdList,objectTypeName,indicatorTypeName,pluginId):
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
                    "value": indicatorTypeName
                    }
                ],

                "objectTypePaths": [
                    {
                    "pathComponents": [
                        objectTypeName
                    ]
                    }
                ],
                "pluginIds": [
                    pluginId
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
