import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from videos.forms import canonical_url, validate_upload


@pytest.mark.parametrize("url", ["http://youtu.be/abcdefghijk", "https://www.youtube.com@localhost/watch?v=abcdefghijk",
                                 "https://youtu.be.evil.test/abcdefghijk", "https://youtube.com:123/watch?v=abcdefghijk"])
def test_forbidden_links(url):
    with pytest.raises(ValidationError):
        canonical_url(url)


def test_canonical_links():
    assert canonical_url("https://youtu.be/abcdefghijk?t=36") == "https://www.youtube.com/watch?v=abcdefghijk"
    assert canonical_url("https://twitch.tv/videos/123") == "https://www.twitch.tv/videos/123"


def test_fake_upload():
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("spoof.mp4", b"not a container", content_type="video/mp4"))


def test_live_links():
    assert canonical_url("https://www.youtube.com/live/abcdefghijk?si=xyz") == "https://www.youtube.com/watch?v=abcdefghijk"
    assert canonical_url("https://www.youtube.com/@channel/live?feature=share") == "https://www.youtube.com/@channel/live"
    assert canonical_url("https://www.twitch.tv/Example_Channel/") == "https://www.twitch.tv/example_channel"
    with pytest.raises(ValidationError):
        canonical_url("https://www.twitch.tv/directory")
