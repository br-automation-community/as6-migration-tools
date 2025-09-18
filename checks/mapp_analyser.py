import os
from utils import utils
from checks import hardware_check

def mappLicenseAnalyser(project_path):
    result = {}
    logical = project_path + "\\Logical"
    physical = project_path + "\\Physical"
    mappView = None
    # scan the logical folder for a mappView folder
    for item in os.listdir(logical):
        if "mappView" in item:
            mappView = item
            break
    if mappView is not None:
        result["mappView"] = {
            "breaseWidgets": utils.load_file_info("licenses","brease_widgets"),
            "uaServerCnt": 0,
            "clientCnt": 0,
            "eventScriptCnt": 0
        }
        folder = logical + "\\" + mappView
        for root, dirs, files in os.walk(folder):
            for file in files:
                if ".content" in file:
                    filePath = os.path.join(root, file) 
                    with open(filePath, encoding="utf8") as item:
                        for line in item:
                            for obj in result["mappView"]["breaseWidgets"]:
                                if "widgets.brease."+obj["name"] in line:
                                    #utils.log("widgets.brease."+obj["name"] + " - " + filePath, severity="INFO",)
                                    #log.append("widgets.brease."+obj["name"] + " - " + filePath)
                                    obj["cnt"] += 1
                    break
    
    folder = physical
    services = utils.load_file_info("licenses","mapp_services")
    result["mappServices"] = {
        "services": []
    }
    result["mappMotion"] = {
        "functions": utils.load_file_info("licenses","mapp_motion")
    }
    result["mappTrak"] = {
        "hardware": [],
        "collisionAvoidance": ""
    }
    for root, dirs, files in os.walk(folder):
        for file in files:
            arr = file.split(".")
            if "assembly" == arr[1]: 
                items = utils.file_value_by_id(os.path.join(root, file), ["Strategy"])
                if len(items) > 0:
                    for item in items:
                        result["mappTrak"]["collisionAvoidance"] = item["value"]
                        if item["value"] == "Variable" or item["value"] == "AdvancedVariable":
                            break

            elif "axis" == arr[1]: 
                pairs = []
                for obj in result["mappMotion"]["functions"]:
                    pairs.append({"type": obj["type"], "cnt": 0})
                items = utils.file_type_count(os.path.join(root, file), pairs)
                for obj in result["mappMotion"]["functions"]:
                    for item in items:
                        if obj["type"] == item["type"]:
                            obj["cnt"] = item["cnt"]

            elif "eventscript" == arr[1]: 
                result["mappView"]["eventScriptCnt"] += 1
            elif "mappconnect" == arr[1]: 
                result["mappConnect"] = {
                    "opcUaServerCnt": 0
                }
                items = utils.file_value_by_id(os.path.join(root, file), ["Url"])
                for item in items:
                    if "Url" in item["name"]:
                        result["mappConnect"]["opcUaServerCnt"] += 1
            elif "mappviewcfg" == arr[1]:
                items = utils.file_value_by_id(os.path.join(root, file), ["MaxClientConnections"])
                for item in items:
                    if "MaxClientConnections" in item["name"]:
                        result["mappView"]["clientCnt"] = int(item["value"])
            elif "uaserver" == arr[1]:
                items = utils.file_value_by_id(os.path.join(root, file), ["IPAddress"])
                for item in items:
                    if "IPAddress" in item["name"]:
                        result["mappView"]["uaServerCnt"] += 1
            
            elif "visionapplication" == arr[1]: 
                result["mappVision"] = {
                    "functions": utils.load_file_info("licenses","mapp_vision")
                }
                pairs = []
                for obj in result["mappVision"]["functions"]:
                    pairs.append({"id": "VfType", "value" : obj["VfType"], "cnt": 0})
                items = utils.file_value_count(os.path.join(root, file), pairs)
                for obj in result["mappVision"]["functions"]:
                    for item in items:
                        if obj["VfType"] == item["value"]:
                            obj["cnt"] = item["cnt"]
        for file in files:
            for service in services:
                for serviceFile in service["file"]:
                    if serviceFile in file:
                        service["cnt"] += 1
        result["mappServices"]["services"] = services

    # count all the hardware in the project
    hardware = hardware_check.count_hardware(folder)
    
    # look for mappTrak hardware

    for item in hardware:
        if "8F1I01" in item:
            result["mappTrak"]["hardware"].append({"module" : item, "cnt" : hardware[item]["cnt"]})

    return result

        