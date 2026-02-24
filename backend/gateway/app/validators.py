import re
from fastapi import HTTPException

_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?$", re.IGNORECASE)
_PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\.]*$")
_BRANCH_RE = re.compile(r"^[\w\-\.\/]+$")


def validate_repo_url(url: str) -> str:
    url = url.strip()
    if not _GITHUB_URL_RE.match(url):
        raise HTTPException(status_code=422, detail="Invalid repo URL — only GitHub HTTPS URLs are accepted")
    return url


def validate_package_name(name: str) -> str:
    name = name.strip()
    if not name or not _PACKAGE_NAME_RE.match(name):
        raise HTTPException(status_code=422, detail="Invalid package name format")
    return name


def validate_branch(branch: str) -> str:
    branch = branch.strip()
    if not branch or not _BRANCH_RE.match(branch):
        raise HTTPException(status_code=422, detail="Invalid branch name")
    return branch


class AppError:
    @staticmethod
    def not_found(resource: str, id: str | None = None):
        detail = f"{resource} not found"
        if id:
            detail += f" (id={id})"
        raise HTTPException(status_code=404, detail=detail)

    @staticmethod
    def forbidden(msg: str = "Access denied"):
        raise HTTPException(status_code=403, detail=msg)

    @staticmethod
    def conflict(msg: str):
        raise HTTPException(status_code=409, detail=msg)

    @staticmethod
    def bad_request(msg: str):
        raise HTTPException(status_code=400, detail=msg)

    @staticmethod
    def service_unavailable(msg: str):
        raise HTTPException(status_code=503, detail=msg)
