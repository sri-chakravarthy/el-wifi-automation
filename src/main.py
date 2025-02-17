
from logger_config import logger
from PasswordEncryption import *
import traceback
from SevOneAppliance import *

import time
import sys



def check_automation_to_execute(AutomationName,interval,LastExecutionTime):
    cur_time = int(time.time())
    if (LastExecutionTime+interval) <= cur_time:
        logger.debug("Automation '"+ AutomationName + "' has elapsed its configured interval. Running it now.")
        return 0
    else:
        time_to_sleep = int((LastExecutionTime+interval)-cur_time)
        logger.debug("Automation '"+ AutomationName + "' has not elapsed its configured interval.Remaining time: " + str(time_to_sleep))
        return time_to_sleep



if __name__ == '__main__':
    
    try:
        loop_count = 0
        while True:


            logger.debug('-----------------------------------------------------------------------------------------------------------');
            #logger.debug('Starting execution of application')

            configurationFile = "etc/config.json"
            #configurationFile = "/opt/app/etc/config.json"
            #keyFile = "/opt/app/env/key.txt"
            keyFile = "env/key.txt"
            with open(keyFile,"r") as keyfile:
                key=keyfile.read()
            EncryptConfigurationFile(configurationFile,keyFile,"ApplianceDetails","List")
            with open(configurationFile, "r") as f:
                try:
                    config = json.load(f)
                except json.decoder.JSONDecodeError as e:
                    logger.error(f"Error loading JSON data: {e}")
                    exit()
            logger.debug(config)

            '''
            #sampleDataIngestFile = "/opt/app/etc/data-ingest-sample.json"
            sampleDataIngestFile = "etc/data-ingest-sample.json"
            with open(sampleDataIngestFile, "r") as f:
                try:
                    ingestData = json.load(f)
                except json.decoder.JSONDecodeError as e:
                    logger.error(f"Error loading JSON data: {e}")
                    exit()
            #logger.debug("Data to be ingested :")
            #logger.debug(ingestData)
            '''
            #Check each automation configured in the configuration file
            max_time_to_sleep = 0
            for automationConfig in config["Automations"]:
                loop_start = int(time.time())
                if(loop_count==0):
                    prev_exec_time = 0                    
                else:
                    prev_exec_time = automationConfig["Previous Exec Time"]
                loop_count += 1
                logger.info(
                "Started automation (loop " + str(loop_count) + ")")

                logger.debug("Automation Name: " + automationConfig["Name"])
                logger.debug("Automation Enabled: " + automationConfig["Enabled"])
                if(automationConfig["Enabled"]==0):
                    logger.debug("Automation '"+ automationConfig["Name"]+ "' is disabled. Continuing with the next automation")
                    continue

                

                if(automationConfig["Name"]== "Delete Unused Devices"):
                    
                    time_to_sleep = check_automation_to_execute(automationConfig["Name"],automationConfig["interval"],automationConfig["Previous Exec Time"])
                    #Get the maximum time this program can sleep before running the next automation
                    if(time_to_sleep!=0):
                        if(time_to_sleep < max_time_to_sleep):
                            max_time_to_sleep = time_to_sleep                                       
                        continue
                    
                    # As we are running this automation now, the max time to sleep , is the automation interval configured
                    max_time_to_sleep = automationConfig["interval"]
                    sevOneApp = SevOneAppliance(config["ApplianceDetails"][0]["IPAddress"],config["ApplianceDetails"][0]["UserName"],DecryptPassword(config["ApplianceDetails"][0]["Password"]["EncryptedPwd"].encode('utf-8'),key))

                    deviceDict = sevOneApp.get_devices_in_device_group(automationConfig["APDeviceGroupPath"])
                    logger.debug("DeviceGroup Details")

                    #To be uncommented
                    #updatedDeviceDict = sevOneApp.get_object_count(deviceDict)
                    #logger.debug(updatedDeviceDict)
                    #sevOneApp.delete_unused_devices(updatedDeviceDict,"1")
                    automationConfig["Previous Exec Time"] = loop_start

                    with open(configurationFile, 'w') as file:
                        json.dump(config, file, indent=4)

                    logger.debug("Updating the configuration with current time:" + str(loop_start))

                elif(automationConfig["Name"]== "WLC Pinning"):


                    # Check if we need to run this automation based on its time interval
                    time_to_sleep = check_automation_to_execute(automationConfig["Name"],automationConfig["interval"],automationConfig["Previous Exec Time"])
                    #Get the maximum time this program can sleep before running the next automation
                    if(time_to_sleep!=0):
                        if(time_to_sleep < max_time_to_sleep):
                            max_time_to_sleep = time_to_sleep                                       
                        continue
                    
                    # As we are running this automation now, the max time to sleep , is the automation interval configured
                    max_time_to_sleep = automationConfig["interval"]
                    sevOneApp = SevOneAppliance(config["ApplianceDetails"][0]["IPAddress"],config["ApplianceDetails"][0]["UserName"],DecryptPassword(config["ApplianceDetails"][0]["Password"]["EncryptedPwd"].encode('utf-8'),key))

                    list_of_new_WLCs= sevOneApp.get_new_WLC_onboarded(automationConfig["WLC Metadata Namespace"],automationConfig["WLC Metadata Attribute"],automationConfig["WLC Metadata Value"],automationConfig["WLC Peer - Device Group Path"])

                    logger.debug("List of new WLCs onboarded:")
                    logger.debug(list_of_new_WLCs)

                    #To be commented / Removed
                    list_of_new_WLCs =["24", "25", "23"]

                    #Check if the new WLCs are Cisco or Aruba
                    list_new_wlc_details = sevOneApp.get_device_details(list_of_new_WLCs)
                  


                    ## Make snmp get to find total number of AP associated. If ApCount = -1, then there was an error in snmpwalk
                    list_new_wlc_details_ap=sevOneApp.get_wlc_access_point_count(list_new_wlc_details,automationConfig["Cisco AP Count OID"],automationConfig["Aruba AP Count OID"])
                    logger.debug("New WLC with APCount details are:")
                    logger.debug(list_new_wlc_details_ap)

                    #Check the capacity of peers which have Wifi Collectors installed
                    peer_list = sevOneApp.get_peer_capacity(automationConfig["WLC Peer - Device Group Path"])
                    logger.debug("Peer Capacity:")
                    logger.debug(peer_list)

                    #Get number of SSIDs of the new WLCs from Metadata
                    wlc_ssid_list = sevOneApp.get_device_metadata_details("WLC Device","SSID_Count",list_of_new_WLCs)


                    #Update the SSID count into the wlc_details_ap list
                    #Create a dictionary to store deviceID-location mapping
                    wlc_ssid_map = {d['DeviceId']: d['Metadata Value'] for d in wlc_ssid_list}
                    # Iterate through each dictionary in list1
                    for d in list_new_wlc_details_ap:
                        # Check if the deviceID exists in the device_location_map
                        if d['DeviceId'] in wlc_ssid_map:
                            # Update the dictionary in list1 with the location from list2
                            d.update({'SSID_Count': wlc_ssid_map[d['DeviceId']]})

                    logger.debug("SSID counts of WLCs:")
                    logger.debug(list_new_wlc_details_ap)

                    #Estimate the number of Objects from the new WLCs
                    no_of_new_wlcs = len(list_new_wlc_details_ap)
                    total_ap_count = 0
                    total_ssid_count = 0
                    for wlc in list_new_wlc_details_ap:
                        total_ssid_count += int(wlc["SSID_Count"]) 
                        if wlc["AP_Count"] > 0:
                            total_ap_count += wlc["AP_Count"]
                        else:
                            logger.debug("Unable to estimate the number of APs in WLC "+ wlc["DeviceName"] + ". Please check SNMP settings on the device or the OID string in the automation Configuration")
                    no_of_wifi_stations = 200
                    wifi_self_mon = 1
                    agg_manfd_objects = no_of_new_wlcs*200
                    no_of_wireless_stations = total_ap_count * 5
                    estimated_no_of_objects = no_of_new_wlcs + (total_ssid_count * no_of_new_wlcs) + agg_manfd_objects + total_ap_count + no_of_wireless_stations

                    logger.debug("Estimated number of objects from new WLCs:" + str(estimated_no_of_objects))


                    #Check which peer can handle the expected object count
                    peer_name_to_pin = ""
                    
                    for peer in peer_list:
                        if (peer["Objects Available"] > estimated_no_of_objects):
                            peer_name_to_pin = peer["Name"]
                            peer_id_to_pin = peer["Id"]
                    logger.debug("The new WLCs can be pinned to the Peer:" + peer_name_to_pin)

                    #Get the wifi Groupname and DeviceGroupId corresponding to that particular Peer
                    if (peer_name_to_pin is None) or (peer_name_to_pin == ""):
                        logger.debug("No peer available with the required capacity to poll the new WLC")
                        logger.debug("Emailing the customer : ")
                        ## Code to email the customer
                        continue
                        #peer_name_to_pin = "SevOne Appliance"


                   
                    # Get the Peer deviceGroup path                    
                    deviceGroupPathDict = automationConfig["WLC Peer - Device Group Path"][peer_name_to_pin]
                    for newWLC in list_new_wlc_details_ap:
                        if re.search("Cisco",newWLC["DeviceVendor"],re.IGNORECASE):
                            newWLC["DeviceGroupPath"] = deviceGroupPathDict["Cisco"]
                        elif re.search("Aruba",newWLC["DeviceVendor"],re.IGNORECASE):
                            newWLC["DeviceGroupPath"] = deviceGroupPathDict["Aruba"]
                        # Pin the WLCs to the deviceGroup
                        sevOneApp.pin_device_to_device_group(newWLC["DeviceId"],newWLC["DeviceGroupPath"])

                        #Update the peer for the device
                        sevOneApp.update_peer_polling_for_device(newWLC["DeviceId"],peer_id_to_pin)
                    
                    logger.debug("New WLC details, updated with DeviceGroup Path to pin:")
                    logger.debug(list_new_wlc_details_ap)

                        
                    
                    # Email the customer




                   



                    automationConfig["Previous Exec Time"] = loop_start
                    with open(configurationFile, 'w') as file:
                        json.dump(config, file, indent=4)

                    logger.debug("Updating the configuration with current time:" + str(loop_start))

            logger.debug("Sleeping for "+ str(max_time_to_sleep) +" seconds.") 
            time.sleep(max_time_to_sleep)


    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"An unexpected error occurred: {tb}")
        sys.exit(2)


