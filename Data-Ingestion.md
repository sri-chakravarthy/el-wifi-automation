```sh
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
```