import os
import sys
from pathlib import Path
from checks import mapp_analyser as ma

from utils import utils


def getTimes(cnt):
    if cnt > 1:
        return "times"
    else:
        return "time"

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    utils.log(
        "This script will check which mapp licenses are need in the project",
        severity="INFO",
    )

    status = "Currently the following mapp technologies are supported:\n"
    status += " - mappView\n"
    status += " - mappConnect\n"
    #status += " - mappTrak\n"
    status += " - mappServices\n"
    status += " - mappVision\n"
    utils.log(status,severity="INFO",)

    analyse = ma.mappLicenseAnalyser(project_path)

    # reporting is done here    
    totalLicenses = []                            
    if analyse["mappView"] is not None:
        
        utils.log("mappView licenses" , severity="INFO",)
        premiumWidgetCnt = 0
        
        for obj in analyse["mappView"]["breaseWidgets"]:
            if obj["cnt"] > 0 and obj["license"] > 0:
                premiumWidgetCnt += 1
        
        if premiumWidgetCnt > 0:
            status = "License " + utils.url("1TCMPVIEWWGT.10-01",) + " is needed du to:\n"
            for obj in analyse["mappView"]["breaseWidgets"]:
                if obj["cnt"] > 0 and obj["license"] > 0:
                    #print(" - widgets.brease." + obj["name"] + " used " + str(obj["cnt"]) + " " + getTimes(obj["cnt"]))
                    status += " - " + utils.url("widgets.brease." + obj["name"]) + " used " + str(obj["cnt"]) + " " + getTimes(obj["cnt"]) + "\n"
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPVIEWWGT.10-01")
                
        if analyse["mappView"]["clientCnt"] > 1:
            status = "License " + utils.url("1TCMPVIEWCLT.10-01",) + " is needed du to:\n"
            status += " - " + utils.url("MaxClientConnections",) + " is configured to " + str(analyse["mappView"]["clientCnt"]) + " more than 1"
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPVIEWCLT.10-01")

        if analyse["mappView"]["uaServerCnt"] > 1:
            status = "License " + utils.url("1TCMPVIEWSRV.10-01",) + " is needed due to:\n"
            status += " - " + utils.url("OpcUaServerConnections",) + " is configured to " + str(analyse["mappView"]["uaServerCnt"]) + " more than 1"
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPVIEWSRV.10-01")

        if analyse["mappView"]["eventScriptCnt"] > 0:
            status = "License " + utils.url("1TC6MPVIEWSCR.20",) + " is needed due to:\n"
            status += " - " + utils.url("Event scripts",) + " is added " + str(analyse["mappView"]["eventScriptCnt"]) + " more than 1"
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TC6MPVIEWSCR.20")

        if premiumWidgetCnt == 0 and analyse["mappView"]["clientCnt"] == 0 and analyse["mappView"]["uaServerCnt"] == 0:
            utils.log("License "+utils.url("1TCMPVIEW.00-01",)+" is sufficient for the project", severity="MANDATORY",)
            totalLicenses.append("1TCMPVIEW.00-01")
        else:
            utils.log("License "+utils.url("1TCMPVIEW.20-01",)+" can be used instead of "+utils.url("1TCMPVIEWWGT.10-01",)+", " + utils.url("1TCMPVIEWCLT.10-01",) + " and " + utils.url("1TCMPVIEWSRV.10-01",), severity="INFO",)
            
    if analyse["mappConnect"] is not None:
        status = ""
        if analyse["mappConnect"]["opcUaServerCnt"] > 0:
            utils.log("mappConnect licenses" , severity="INFO",)
            status = "License " + utils.url("1TC6MPVIEWCON.20",) + " is needed due to:\n"
            status += " - " + utils.url("MappConnect OPC UA Server",) + " is configured to " + str(analyse["mappConnect"]["opcUaServerCnt"]) + " more than 0"
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TC6MPVIEWCON.20")

    if analyse["mappTrak"] is not None:
        status = ""
        if analyse["mappTrak"]["collisionAvoidance"] == "Variable" or analyse["mappTrak"]["collisionAvoidance"] == "AdvancedVariable":
            utils.log("mappTrak licenses" , severity="INFO",)
            status = "License " + utils.url("1TCMPTRAK.20-01",) + " is needed due to:\n"
            status += " - " + utils.url("MappTrak Collision Avoidance",) + " is configured to " + str(analyse["mappTrak"]["collisionAvoidance"])
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPTRAK.20-01")
        elif len(analyse["mappTrak"]["hardware"]) > 0:
            utils.log("mappTrak licenses" , severity="INFO",)
            status = "License " + utils.url("1TCMPTRAK.10-01",) + " is needed due to the following hardware has been added:\n"

            for item in analyse["mappTrak"]["hardware"]:
                status += " - " + utils.url(item["module"],) + " x " + str(item["cnt"])
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPTRAK.10-01")
    
    if analyse["mappServices"] is not None:
        addService = 0
        status = ""
        for obj in analyse["mappServices"]["services"]:
            if obj["cnt"] > 0 and obj["license"] > 0:
                addService = 1
                status += " - " + utils.url("mapp" + obj["name"]) + " used " + str(obj["cnt"]) + " " + getTimes(obj["cnt"]) + "\n"
        if addService:
            utils.log("mappServices licenses" , severity="INFO",)
            status = "License " + utils.url("1TCMPSERVICE.10-01",) + " is needed due to:\n" + status
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPSERVICE.10-01")
    
    if analyse["mappMotion"] is not None:
        status = ""
        for obj in analyse["mappMotion"]["functions"]:
            if obj["type"] == "axis":
                if obj["cnt"] > 3:
                    


                    status = "License " + utils.url("1TCMPAXIS.10-01",) + " is needed due to:\n" + status
                    status += " - " + utils.url(obj["name"]) + " used " + str(obj["cnt"]) + " " + getTimes(obj["cnt"]) + "\n"
                    utils.log(status, severity="MANDATORY",)
                    totalLicenses.append("1TCMPAXIS.10-01")


    if analyse["mappVision"] is not None:
        addFunction = 0
        status = ""
        for obj in analyse["mappVision"]["functions"]:
            if obj["cnt"] > 0 and obj["license"] > 0:
                addFunction = 1
                status += " - " + utils.url(obj["name"]) + " used " + str(obj["cnt"]) + " " + getTimes(obj["cnt"]) + "\n"
                
        if addFunction:
            status = "License " + utils.url("1TCMPVISION.10-01",) + " is needed due to:\n" + status
            utils.log(status, severity="MANDATORY",)
            totalLicenses.append("1TCMPVISION.10-01")

    # total licenses
    licenses = utils.load_file_info("licenses","licenses")
    utils.log("Total licenses needed:", severity="MANDATORY",)
    for item in totalLicenses:
        name = ""
        for license in licenses:
            if item in license:
                name = license[item]['name']
                break
        
        print(" - " + utils.url(item,) + " - " + name)

if __name__ == "__main__":
    main()
