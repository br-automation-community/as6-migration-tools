import re


# Check the project name and path for invalid characters
# As opposed to what's in the help, we need to allow : and \ and / as well since these are valid
# path separators
def check_project_path_and_name(path, name, log, verbose=False):
    log("─" * 80 + "\nChecking path and project for invalid characters...")

    project_name_pattern = r"^(\w+)\.apj$"
    project_path_pattern = r"^[\w :\\/!(){}+\-@\.\^=]+$"
    if not re.fullmatch(project_path_pattern, path, flags=re.ASCII) or not re.fullmatch(
        project_name_pattern, name, flags=re.ASCII
    ):
        log(
            "Invalid path or project name, see AS4/Migration",
            severity="ERROR",
        )
