import os
import sys
from pathlib import Path
from checks import mapp_analyzer as ma

from utils import utils


def get_amount(cnt):
    return f"{cnt} {'time' if cnt == 1 else 'times'}"


def check_mapp_view(mapp_view) -> list:
    if mapp_view is None:
        return []

    licenses = []
    premium_widget_cnt = 0

    utils.log(
        "mappView licenses",
        severity="INFO",
    )

    for obj in mapp_view["breaseWidgets"]:
        if obj["cnt"] > 0 and obj["license"] > 0:
            premium_widget_cnt += 1

    if premium_widget_cnt > 0:
        status = f"License {utils.url('1TCMPVIEWWGT.10-01')} is needed due to:"
        for obj in mapp_view["breaseWidgets"]:
            if obj["cnt"] > 0 and obj["license"] > 0:
                status += (
                    f"\n - {utils.url(f'widgets.brease.{obj["name"]}')} used "
                    f"{get_amount(obj['cnt'])}\n"
                )

        utils.log(
            status,
            severity="MANDATORY",
        )
        licenses.append("1TCMPVIEWWGT.10-01")

    if mapp_view["clientCnt"] > 1:
        utils.log(
            f"License {utils.url('1TCMPVIEWCLT.10-01')} is needed due to:\n"
            f" - {utils.url('MaxClientConnections')} is configured to "
            f"more than once ({mapp_view['clientCnt']})",
            severity="MANDATORY",
        )
        licenses.append("1TCMPVIEWCLT.10-01")

    if mapp_view["uaServerCnt"] > 1:
        utils.log(
            f"License {utils.url('1TCMPVIEWSRV.10-01')} is needed:\n"
            f" - {utils.url('OpcUaServerConnections')} is configured to "
            f"more than once ({get_amount(mapp_view['uaServerCnt'])})",
            severity="MANDATORY",
        )
        licenses.append("1TCMPVIEWSRV.10-01")

    if mapp_view["eventScriptCnt"] > 0:
        utils.log(
            f"License {utils.url('1TC6MPVIEWSCR.20')} is needed:\n"
            f" - {utils.url('Event scripts')} is added "
            f"{get_amount(mapp_view['eventScriptCnt'])}",
            severity="MANDATORY",
        )
        licenses.append("1TC6MPVIEWSCR.20")

    if (
        premium_widget_cnt == 0
        and mapp_view["clientCnt"] == 0
        and mapp_view["uaServerCnt"] == 0
    ):
        utils.log(
            f"License {utils.url('1TCMPVIEW.00-01')} is sufficient for the project",
            severity="MANDATORY",
        )
        licenses.append("1TCMPVIEW.00-01")
    else:
        utils.log(
            f"License {utils.url('1TCMPVIEW.20-01')} can be used instead of "
            f"{utils.url('1TCMPVIEWWGT.10-01')}, {utils.url('1TCMPVIEWCLT.10-01')} and "
            f"{utils.url('1TCMPVIEWSRV.10-01')}",
            severity="INFO",
        )
    return licenses


def check_mapp_connect(mapp_connect) -> list:
    if mapp_connect is None:
        return []

    licenses = []

    if mapp_connect["opcUaServerCnt"] > 0:
        utils.log(
            "mappConnect licenses",
            severity="INFO",
        )
        utils.log(
            f"License {utils.url('1TC6MPVIEWCON.20')} is needed due to:\n"
            f" - {utils.url('MappConnect OPC UA Server')} is configured to "
            f"{get_amount(mapp_connect['opcUaServerCnt'])}",
            severity="MANDATORY",
        )
        licenses.append("1TC6MPVIEWCON.20")
    return licenses


def check_mapp_trak(mapp_trak) -> list:
    if mapp_trak is None:
        return []

    licenses = []

    if (
        mapp_trak["collisionAvoidance"] == "Variable"
        or mapp_trak["collisionAvoidance"] == "AdvancedVariable"
    ):
        utils.log(
            "mappTrak licenses",
            severity="INFO",
        )
        utils.log(
            f"License {utils.url('1TCMPTRAK.20-01')} is needed due to:\n"
            f" - {utils.url('MappTrak Collision Avoidance')} is configured to "
            f"{get_amount(mapp_trak['collisionAvoidance'])}",
            severity="MANDATORY",
        )
        licenses.append("1TCMPTRAK.20-01")
    elif len(mapp_trak["hardware"]) > 0:
        utils.log(
            "mappTrak licenses",
            severity="INFO",
        )
        status = (
            f"License {utils.url('1TCMPTRAK.10-01')} is needed because the "
            "following hardware is used:"
        )
        for item in mapp_trak["hardware"]:
            status += f"\n - {utils.url(item['module'])} x {item['cnt']}"
        utils.log(
            status,
            severity="MANDATORY",
        )
        licenses.append("1TCMPTRAK.10-01")
    return licenses


def check_mapp_services(mapp_services) -> list:
    if mapp_services is None:
        return []

    licenses = []
    status = ""
    for obj in mapp_services["services"]:
        if obj["cnt"] > 0 and obj["license"] > 0:
            status += (
                f" - {utils.url(f'mapp{obj["name"]}')} used {get_amount(obj['cnt'])}\n"
            )
    if status:
        utils.log(
            "mappServices licenses",
            severity="INFO",
        )
        utils.log(
            f"License {utils.url('1TCMPSERVICE.10-01')} is needed due to:\n{status}",
            severity="MANDATORY",
        )
        licenses.append("1TCMPSERVICE.10-01")
    return licenses


def check_mapp_motion(mapp_motion) -> list:
    if mapp_motion is None:
        return []

    licenses = []
    for obj in mapp_motion["functions"]:
        if obj["type"] == "axis":
            if obj["cnt"] > 3:
                utils.log(
                    f"License {utils.url('1TCMPAXIS.10-01')} is needed due to:\n"
                    f" - {utils.url(obj['name'])} used {get_amount(obj['cnt'])}\n",
                    severity="MANDATORY",
                )
                licenses.append("1TCMPAXIS.10-01")
    return licenses


def check_mapp_vision(mapp_vision) -> list:
    if mapp_vision is None:
        return []

    licenses = []
    status = ""
    for obj in mapp_vision["functions"]:
        if obj["cnt"] > 0 and obj["license"] > 0:
            status += f" - {utils.url(obj['name'])} used {get_amount(obj['cnt'])}\n"

    if status:
        utils.log(
            f"License {utils.url('1TCMPVISION.10-01')} is needed due to:\n{status}",
            severity="MANDATORY",
        )
        licenses.append("1TCMPVISION.10-01")
    return licenses


def main():
    project_path = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    apj_file = utils.get_and_check_project_file(project_path)

    utils.log(f"Project path validated: {project_path}")
    utils.log(f"Using project file: {apj_file}\n")

    utils.log(
        "This script will check which mapp licenses are need in the project",
        severity="INFO",
    )

    supported_services = [
        "mappView",
        "mappConnect",
        "mappTrak",
        "mappServices",
        "mappVision",
    ]
    status = "Currently the following mapp technologies are supported:"
    for service in supported_services:
        status += f"\n - {service}"
    utils.log(
        status,
        severity="INFO",
    )

    analyse = ma.mapp_license_analyzer(project_path)

    # reporting is done here
    total_licenses = []
    total_licenses += check_mapp_view(analyse["mappView"])
    total_licenses += check_mapp_connect(analyse["mappConnect"])
    total_licenses += check_mapp_trak(analyse["mappTrak"])
    total_licenses += check_mapp_services(analyse["mappServices"])
    total_licenses += check_mapp_motion(analyse["mappMotion"])
    total_licenses += check_mapp_vision(analyse["mappVision"])

    # total licenses
    licenses = utils.load_file_info("licenses", "licenses")
    output = ""
    for item in total_licenses:
        name = next(
            (lic[item]["name"] for lic in licenses if item in lic),
            "",
        )
        output += f"\n - {utils.url(item)} - {name}"

    utils.log(
        f"Total licenses needed: {output}",
        severity="MANDATORY",
    )


if __name__ == "__main__":
    main()
