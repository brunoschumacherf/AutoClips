import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

API = "https://open.tiktokapis.com/v2"
CHUNK_BYTES = 32 * 1024**2


def enabled():
    return all((settings.TIKTOK_CLIENT_KEY, settings.TIKTOK_CLIENT_SECRET,
                settings.TIKTOK_REDIRECT_URI, settings.OAUTH_ENCRYPTION_KEY))


def authorization_url(state):
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": settings.TIKTOK_CLIENT_KEY, "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        "scope": "user.info.basic,video.upload", "response_type": "code", "state": state,
    })


def request_json(request, timeout=20):
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    error = result.get("error")
    if error and (not isinstance(error, dict) or error.get("code") != "ok"):
        raise ValueError("TikTok rejected the request")
    return result


def token(**fields):
    data = urlencode({"client_key": settings.TIKTOK_CLIENT_KEY, "client_secret": settings.TIKTOK_CLIENT_SECRET, **fields})
    return request_json(Request(f"{API}/oauth/token/", data=data.encode()))


def api(path, access, **payload):
    return request_json(Request(f"{API}/{path}", data=json.dumps(payload).encode() if payload else None,
                                headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"}))["data"]


def grant_for_code(code):
    grant = token(grant_type="authorization_code", code=code, redirect_uri=settings.TIKTOK_REDIRECT_URI)
    if "video.upload" not in grant.get("scope", "").split(","):
        raise ValueError("The TikTok account did not grant video.upload")
    profile = api("user/info/?fields=open_id,display_name", grant["access_token"])["user"]
    return profile["open_id"], profile["display_name"], grant


def upload(publication, access):
    field = publication.version.output
    size = field.size
    if not 0 < size <= 4 * 1024**3:
        raise ValueError("Unsupported TikTok file size")
    chunk_size = size if size <= 64 * 1024**2 else CHUNK_BYTES
    chunk_count = size // chunk_size
    init = api("post/publish/inbox/video/init/", access, source_info={
        "source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size, "total_chunk_count": chunk_count,
    })
    url = init["upload_url"]
    endpoint = urlsplit(url)
    if endpoint.scheme != "https" or not (endpoint.hostname or "").endswith(".tiktokapis.com"):
        raise ValueError("Unexpected TikTok upload endpoint")
    with field.open("rb") as stream:
        offset = 0
        for index in range(chunk_count):
            length = size - offset if index == chunk_count - 1 else chunk_size
            data = stream.read(length)
            if len(data) != length:
                raise OSError("Incomplete TikTok source read")
            end = offset + length - 1
            headers = {"Content-Type": "video/mp4", "Content-Length": str(length),
                       "Content-Range": f"bytes {offset}-{end}/{size}"}
            with urlopen(Request(url, data=data, method="PUT", headers=headers), timeout=120):
                pass
            offset = end + 1
    return init["publish_id"]


def upload_status(identifier, access):
    return api("post/publish/status/fetch/", access, publish_id=identifier)["status"]
