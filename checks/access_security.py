# checks/access_security.py
import re
from pathlib import Path

from utils import utils


def process_ansl_authentication(file_path: Path) -> list:
    """Return [("AnslAuthentication", file_path)] if Value=\"1\" is present, else []."""
    content = utils.read_file(file_path)
    pat = re.compile(
        r'ID\s*=\s*["\']AnslAuthentication["\']\s+[^>]*Value\s*=\s*["\']1["\']',
        re.IGNORECASE,
    )
    return [("AnslAuthentication", file_path)] if pat.search(content) else []


def _find_user_role_system_dirs_deep(physical_path: Path) -> dict:
    """
    Find all .../AccessAndSecurity/UserRoleSystem anywhere under Physical/.
    Returns: dict[config_name -> list[Path]]
    """
    result = {}
    if not physical_path or not Path(physical_path).exists():
        return result
    for urs in physical_path.rglob("UserRoleSystem"):
        if not urs.is_dir():
            continue
        if urs.parent.name != "AccessAndSecurity":
            continue
        # derive top-level configuration name (first path segment under Physical/)
        try:
            rel = urs.relative_to(physical_path)
            config_name = rel.parts[0] if rel.parts else "(unknown)"
        except Exception:
            config_name = "(unknown)"
        result.setdefault(config_name, []).append(urs)
    return result


def check_access_security(physical_path: Path, log, verbose: bool = False):
    """
    Access & Security checks scoped to Physical/...:
      1) Remind about password hashing change in AS6 (re-enter all user passwords).
      2) Validate AccessAndSecurity/UserRoleSystem exists (any depth) and has .user/.role.
      3) Scan all .hw for AnslAuthentication=1 and warn before transfer.
    """
    log(
        utils.section_header(
            "access-security",
            "Checking Access & Security (UserRoleSystem + ANSL authentication)...",
        )
    )

    # (1) Global reminder about changed hashing algorithm in AS6
    log(
        "Access & Security: Password hashing algorithm changed in AS6. (AS6/Migration)"
        "\n - You must re-enter the password for all users configured in the 'AccessAndSecurity/UserRoleSystem'."
        "\n - It is no longer possible to authenticate using the old stored password from the AS 4.12 project.",
        when="AS6",
        severity="MANDATORY",
    )

    # (2) Validate UserRoleSystem (deep search)
    urs_map = _find_user_role_system_dirs_deep(Path(physical_path))
    if not urs_map:
        log(
            "Access & Security UserRoleSystem not found under Physical/.../AccessAndSecurity/UserRoleSystem."
            "\n - Create at least one admin user (.user) and role (.role).",
            when="AS6",
            severity="MANDATORY",
        )
    else:
        for cfg, dirs in sorted(urs_map.items()):
            for urs_dir in dirs:
                users = list(urs_dir.glob("*.user"))
                roles = list(urs_dir.glob("*.role"))
                if not users or not roles:
                    log(
                        f"[{cfg}] Users/Roles missing in UserRoleSystem at: {urs_dir}"
                        f"\n - Found {len(users)} .user and {len(roles)} .role file(s)."
                        "\n - Create at least one enabled admin user and role.",
                        when="AS6",
                        severity="MANDATORY",
                    )
                elif verbose:
                    log(
                        f"[{cfg}] UserRoleSystem OK at {urs_dir} (users: {len(users)}, roles: {len(roles)})",
                        severity="INFO",
                    )

    # (3) ANSL authentication in .hw (parallel scan; no keyword args)
    ansl_results = utils.scan_files_parallel(
        physical_path,
        [".hw"],
        process_ansl_authentication,
    )

    if ansl_results:
        log(
            "ANSL authentication is enabled and it uses Access & Security user management."
            "\n - Update all user passwords before transferring the project in AS6, otherwise you will be locked out of the target system.",
            when="AS6",
            severity="MANDATORY",
        )
    else:
        if verbose:
            log("ANSL authentication not enabled in any .hw files.", severity="INFO")
