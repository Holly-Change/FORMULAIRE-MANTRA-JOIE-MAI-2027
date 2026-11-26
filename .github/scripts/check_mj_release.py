"""Check an MJ release before writing to Apps Script or GitHub."""
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MAX_BYTES = 24 * 1024 * 1024
REQUIRED = (
    "1-Apps-Script/Code.gs",
    "1-Apps-Script/Portail.gs",
    "1-Apps-Script/Equipe.gs",
    "2-GitHub/index.html",
    "2-GitHub/equipe.html",
    "2-GitHub/manual.html",
    "2-GitHub/sw.js",
)


def request(url, service, *, token=None, data=None, limit=MAX_BYTES):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    query = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(query, timeout=45) as response:
            body = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        raise ValueError(f"{service} returned HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError(f"{service} did not respond") from None
    if len(body) > limit:
        raise ValueError(f"{service} response exceeded the size limit")
    return body


def drive_pack(file_id):
    auth = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }
    token = json.loads(request(
        "https://oauth2.googleapis.com/token", "Google authorization",
        data=urllib.parse.urlencode(auth).encode(), limit=65536,
    ))["access_token"]
    return request(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                   "Google Drive", token=token)


def check_pack(data, version):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if sum(item.file_size for item in entries) > 4 * MAX_BYTES:
            raise ValueError("Release package is too large once expanded")
        names = [item.filename for item in entries]
        if len(names) != len(set(names)):
            raise ValueError("Release package has duplicate filenames")
        for name in REQUIRED:
            if name not in names or not archive.getinfo(name).file_size:
                raise ValueError(f"Missing or empty release file: {name}")
        for name in ("2-GitHub/index.html", "2-GitHub/equipe.html"):
            if version.encode() not in archive.read(name):
                raise ValueError(f"{name} does not contain the requested version")
        if archive.testzip() is not None:
            raise ValueError("Release package has an invalid checksum")


def main():
    version = os.environ["MJ_RELEASE_VERSION"]
    if not re.fullmatch(r"v\d+\.\d+-2027", version):
        raise ValueError("Release version must look like v3.86-2027")
    if len(sys.argv) == 2:
        with open(sys.argv[1], "rb") as local:
            data = local.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Release package exceeds the download size limit")
    else:
        file_id = os.environ["MJ_RELEASE_FILE_ID"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{15,200}", file_id):
            raise ValueError("Enter the file ID from the Google Drive ZIP link")
        data = drive_pack(file_id)
    check_pack(data, version)
    print(f"Release package checks passed for {version}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        sys.exit(f"Release check failed: {error}")
