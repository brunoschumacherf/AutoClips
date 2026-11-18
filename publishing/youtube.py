import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def enabled():
    return all((settings.YOUTUBE_CLIENT_ID, settings.YOUTUBE_CLIENT_SECRET, settings.YOUTUBE_REDIRECT_URI,
                settings.OAUTH_ENCRYPTION_KEY))


def authorization_url(state, challenge):
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": settings.YOUTUBE_CLIENT_ID, "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code", "scope": SCOPES, "state": state, "access_type": "offline",
        "prompt": "consent", "code_challenge": challenge, "code_challenge_method": "S256",
    })


def token(**fields):
    payload = urlencode({"client_id": settings.YOUTUBE_CLIENT_ID, "client_secret": settings.YOUTUBE_CLIENT_SECRET, **fields})
    with urlopen(Request(TOKEN_ENDPOINT, data=payload.encode()), timeout=20) as response:
        return json.load(response)


def channel(access_token):
    query = urlencode({"part": "snippet", "mine": "true"})
    with urlopen(Request(f"{API}/channels?{query}", headers={"Authorization": f"Bearer {access_token}"}), timeout=20) as response:
        item = json.load(response)["items"][0]
        return item["id"], item["snippet"]["title"]


def upload(publication, access_token):
    field = publication.version.output
    size = field.size
    request = Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps({"snippet": {"title": publication.title, "description": publication.description},
                         "status": {"privacyStatus": "private"}}).encode(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
    )
    with urlopen(request, timeout=20) as response:
        session = response.headers["Location"]
    endpoint = urlsplit(session)
    if endpoint.scheme != "https" or endpoint.hostname not in {"www.googleapis.com", "upload.youtube.com"}:
        raise ValueError("Unexpected YouTube upload endpoint")
    with field.open("rb") as source:
        request = Request(session, data=source, method="PUT", headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
        with urlopen(request, timeout=180) as response:
            return json.load(response)["id"]


def remote_status(remote_id, access_token):
    query = urlencode({"part": "status", "id": remote_id})
    request = Request(f"{API}/videos?{query}", headers={"Authorization": f"Bearer {access_token}"})
    with urlopen(request, timeout=20) as response:
        items = json.load(response)["items"]
        return items[0]["status"]["uploadStatus"] if items else "deleted"
