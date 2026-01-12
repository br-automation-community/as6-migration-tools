import re
from pathlib import Path

from lxml import etree

from utils import utils


def check_mapp_view(apj_path: Path, log, verbose=False):
    """
    Checks for the presence of mappView settings files in the specified directory.
    """
    log(
        utils.section_header(
            "mapp-view", "Checking mappView version in project file..."
        )
    )

    # Check for mappView line in the .apj file
    for line in utils.read_file(apj_path).splitlines():
        if "<mappView " in line and "Version=" in line:
            match = re.search(r'Version="(\d+)\.(\d+)', line)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                version = f"{major}.{minor}"

                log(f"Found usage of mappView (Version: {version})", severity="INFO")
                log(
                    f"Several security settings will be enforced after the migration. While we do recommend to use the new settings for better security, here are the steps to restore the previous behavior:"
                    "\n"
                    "\n- To allow access without a certificate"
                    "\n  Change the following settings in the OPC Client/Server configuration (Configuration View/Connectivity/OpcUaCs/UaCsConfig.uacfg):"
                    "\n  ClientServerConfiguration->Security->MessageSecurity->SecurityPolicies->None: Enabled"
                    "\n"
                    "\n- User login will be enabled by default. To allow anonymous access"
                    "\n  Change the following settings in mappView configuration (Configuration View/mappView/Config.mappviewcfg):"
                    "\n  MappViewConfiguration->Server Configuration->Startup User: anonymous token"
                    "\n"
                    "\n- Change the following settings in the OPC Client/Server configuration (Configuration View/Connectivity/OpcUaCs/UaCsConfig.uacfg):"
                    "\n  Click on the two green blocks at the top where it says 'Change Advanced Parameter Visibility'"
                    "\n  ClientServerConfiguration->Security->Authentication->Authentication Methods->Anonymous: Enabled"
                    "\n  ClientServerConfiguration->Security->Authorization->AnonymousAccess->User Role 1: Everyone"
                    "\n"
                    "\n- Change the following settings in the User role system (Configuration View/AccessAndSecurity/UserRoleSystem/User.user):"
                    '\n  Assign the role "BR_Engineer" to the user "Anonymous". Create that user if it doesn\'t already exist, assign no password.'
                    "\n"
                    "\n- To allow access to a File device from a running mappView application, it is now required to explicitly whitelist it for reading:"
                    "\n  Open the mappView server configuration file (Configuration View/mappView/Config.mappviewcfg)"
                    '\n  Check "Change Advanced Parameter Visibility" button in the editor toolbar'
                    '\n  Enter your accessed File device "Name" under "MappViewConfiguration->Server configuration->File device whitelist"',
                    when="AS6",
                    severity="WARNING",
                )

            # check for specific widgets
            # Namespace mappings
            ns = {
                "c": "http://www.br-automation.com/iat2015/contentDefinition/v2",
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            }
            logical_path = apj_path.parent / "Logical"
            try:
                for content_path in logical_path.rglob("*.content"):
                    tree = etree.parse(str(content_path))
                    root_elem = tree.getroot()

                    for widget in root_elem.xpath(".//c:Widget", namespaces=ns):
                        xsi_type = widget.get(f"{{{ns['xsi']}}}type")
                        if xsi_type in {
                            "widgets.brease.AuditList",
                            "widgets.brease.TextPad",
                            "widgets.brease.UserList",
                            "widgets.brease.MotionPad",
                        }:
                            log(
                                "Found use of AuditList, UserList, TextPad or MotionPad widgets that requires the role of BR_Engineer"
                                "\n - Check in the following (Configuration View/AccessAndSecurity/UserRoleSystem/User.user) that a user with role BR_Engineer is present",
                                severity="INFO",
                            )
            except etree.ParseError as e:
                log(f"XML parsing error in {content_path}: {e}", severity="ERROR")
            except Exception as e:
                log(
                    f"Unexpected error while processing {content_path}: {e}",
                    severity="ERROR",
                )

    if verbose:
        # Walk through all directories
        physical_path = apj_path.parent / "Physical"
        for mappView_path in physical_path.rglob("mappView"):
            if mappView_path.is_dir():
                log(f"mappView folders found at: {mappView_path}", severity="INFO")
