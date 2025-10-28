import requests


def get_changelog_between_versions(old_version: str, new_version: str) -> dict:
    """
    Get changelog between two versions using GitHub API.
    """
    url = f"https://api.github.com/repos/br-automation-community/as6-migration-tools/compare/v{old_version}...v{new_version}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return {
                "success": False,
                "changelog": "",
                "commit_count": 0,
                "error": f"Version v{old_version} or v{new_version} not found",
            }
        elif response.status_code != 200:
            return {
                "success": False,
                "changelog": "",
                "commit_count": 0,
                "error": f"GitHub API Error: {response.status_code}",
            }

        data = response.json()
        commits = data.get("commits", [])

        if not commits:
            return {
                "success": True,
                "changelog": "No commits found between the specified versions.",
                "commit_count": 0,
                "error": "",
            }

        # Create changelog from commit messages
        changelog_lines = [f"Changes since your local version v{old_version}:\n"]
        for commit in reversed(commits):  # Oldest first
            message = commit["commit"]["message"].split("\n")[0]  # Only first line
            changelog_lines.append(f"- {message}")

        changelog = "\n".join(changelog_lines)

        return {
            "success": True,
            "changelog": changelog,
            "commit_count": len(commits),
            "error": "",
        }

    except requests.RequestException as e:
        return {
            "success": False,
            "changelog": "",
            "commit_count": 0,
            "error": f"Network error: {str(e)}",
        }
    except Exception as e:
        return {
            "success": False,
            "changelog": "",
            "commit_count": 0,
            "error": f"Unknown error: {str(e)}",
        }
