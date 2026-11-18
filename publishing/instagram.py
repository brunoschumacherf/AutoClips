import json
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

GRAPH = "https://graph.instagram.com"


def enabled():
    return all((settings.INSTAGRAM_APP_ID, settings.INSTAGRAM_APP_SECRET, settings.INSTAGRAM_REDIRECT_URI,
                settings.OAUTH_ENCRYPTION_KEY, settings.STORAGES["default"]["BACKEND"] == "storages.backends.s3.S3Storage"))


def authorization_url(state):
    return "https://www.instagram.com/oauth/authorize?" + urlencode({
        "client_id": settings.INSTAGRAM_APP_ID, "redirect_uri": settings.INSTAGRAM_REDIRECT_URI,
        "scope": "instagram_business_basic,instagram_business_content_publish",
        "response_type": "code", "state": state, "enable_fb_login": "0",
    })


def request_json(url, fields=None, *, access=None):
    data = urlencode(fields).encode() if fields is not None else None
    headers = {"Authorization": f"Bearer {access}"} if access else {}
    with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
        return json.load(response)


def graph(path, *, access, fields=None, query=None):
    url = f"{GRAPH}/{settings.INSTAGRAM_API_VERSION}/{path}"
    if query:
        url += "?" + urlencode(query)
    return request_json(url, fields, access=access)


def grant_for_code(code):
    short = request_json("https://api.instagram.com/oauth/access_token", {
        "client_id": settings.INSTAGRAM_APP_ID, "client_secret": settings.INSTAGRAM_APP_SECRET,
        "grant_type": "authorization_code", "redirect_uri": settings.INSTAGRAM_REDIRECT_URI, "code": code,
    })
    grant = request_json(f"{GRAPH}/access_token?" + urlencode({
        "grant_type": "ig_exchange_token", "client_secret": settings.INSTAGRAM_APP_SECRET,
        "access_token": short["access_token"],
    }))["access_token"]
    profile = graph("me", access=grant, query={"fields": "user_id,username"})
    account_id = str(profile["user_id"])
    if not account_id.isascii() or not account_id.isdigit():
        raise ValueError("Invalid Instagram account identifier")
    return account_id, profile["username"], grant


def create_container(publication, access):
    output = publication.version.output
    url = output.storage.url(output.name, expire=3600)
    if urlsplit(url).scheme != "https":
        raise ValueError("The Instagram API requires an HTTPS video URL")
    caption = "\n\n".join(text for text in (publication.title, publication.description) if text)
    return graph(f"{publication.account.external_id}/media", access=access, fields={
        "media_type": "REELS", "video_url": url, "caption": caption[:2200],
    })["id"]


def container_status(container, access):
    return graph(container, access=access, query={"fields": "status_code"})["status_code"]


def publish(publication, access):
    return graph(f"{publication.account.external_id}/media_publish", access=access,
                 fields={"creation_id": publication.remote_id})["id"]
