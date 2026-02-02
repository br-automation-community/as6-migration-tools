from pathlib import Path

from utils import utils
from checks import hardware_check


def mapp_license_analyzer(project_path: Path):
    result = {}
    logical = project_path / "Logical"
    physical = project_path / "Physical"
    mapp_view_path = None
    # scan the logical folder for a mappView folder
    for item in logical.iterdir():
        if "mappView" in item.name:
            mapp_view_path = item
            break

    result["mappView"] = None
    if mapp_view_path is not None:
        result["mappView"] = {
            "breaseWidgets": utils.load_file_info("licenses", "brease_widgets"),
            "uaServerCnt": 0,
            "clientCnt": 0,
            "eventScriptCnt": 0,
        }
        for file in mapp_view_path.rglob("*"):
            if file.is_file() and ".content" in file.name:
                lines = utils.read_file(file).splitlines()
                for line in lines:
                    for obj in result["mappView"]["breaseWidgets"]:
                        if "widgets.brease." + obj["name"] in line:
                            obj["cnt"] += 1

    services = utils.load_file_info("licenses", "mapp_services")
    result["mappServices"] = {"services": []}
    result["mappMotion"] = {
        "functions": utils.load_file_info("licenses", "mapp_motion")
    }
    result["mappTrak"] = {"hardware": [], "collisionAvoidance": ""}
    result["mappConnect"] = None
    result["mappVision"] = None
    for file in physical.rglob("*"):
        if not file.is_file():
            continue

        if file.suffix == ".assembly":
            items = utils.file_value_by_id(file, ["Strategy"])
            if len(items) > 0:
                for item in items:
                    result["mappTrak"]["collisionAvoidance"] = item["value"]
                    if (
                        item["value"] == "Variable"
                        or item["value"] == "AdvancedVariable"
                    ):
                        break

        elif file.suffix == ".axis":
            pairs = []
            for obj in result["mappMotion"]["functions"]:
                pairs.append({"type": obj["type"], "cnt": 0})
            items = utils.file_type_count(file, pairs)
            for obj in result["mappMotion"]["functions"]:
                for item in items:
                    if obj["type"] == item["type"]:
                        obj["cnt"] = item["cnt"]

        elif file.suffix == ".eventscript":
            result["mappView"]["eventScriptCnt"] += 1
        elif file.suffix == ".mappconnect":
            result["mappConnect"] = {"opcUaServerCnt": 0}
            items = utils.file_value_by_id(file, ["Url"])
            for item in items:
                if "Url" in item["name"]:
                    result["mappConnect"]["opcUaServerCnt"] += 1
        elif file.suffix == ".mappviewcfg":
            items = utils.file_value_by_id(file, ["MaxClientConnections"])
            for item in items:
                if "MaxClientConnections" in item["name"]:
                    result["mappView"]["clientCnt"] = int(item["value"])
        elif file.suffix == ".uaserver":
            items = utils.file_value_by_id(file, ["IPAddress"])
            for item in items:
                if "IPAddress" in item["name"]:
                    result["mappView"]["uaServerCnt"] += 1

        elif file.suffix == ".visionapplication":
            result["mappVision"] = {
                "functions": utils.load_file_info("licenses", "mapp_vision")
            }
            pairs = []
            for obj in result["mappVision"]["functions"]:
                pairs.append({"id": "VfType", "value": obj["VfType"], "cnt": 0})
            items = utils.file_value_count(file, pairs)
            for obj in result["mappVision"]["functions"]:
                for item in items:
                    if obj["VfType"] == item["value"]:
                        obj["cnt"] = item["cnt"]

        for service in services:
            for serviceFile in service["file"]:
                if serviceFile in file.name:
                    service["cnt"] += 1
        result["mappServices"]["services"] = services

    # count all the hardware in the project
    hardware = hardware_check.count_hardware(physical)

    # look for mappTrak hardware
    for item in hardware:
        if "8F1I01" in item:
            result["mappTrak"]["hardware"].append(
                {"module": item, "cnt": hardware[item]["cnt"]}
            )

    return result
