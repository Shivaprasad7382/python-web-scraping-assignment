import pytest
import requests

from config import Config
from http_client import FetchError, HttpClient


class FakeResp:
    def __init__(self, status, text=""):
        self.status_code, self.text, self.encoding = status, text, None


class FakeSession:
    def __init__(self, responses):
        self.responses, self.headers, self.calls = list(responses), {}, 0

    def get(self, url, timeout=None):
        if url.endswith("/robots.txt"):
            return FakeResp(404)
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(responses, retries=3):
    cfg = Config(max_retries=retries, backoff_base=1.0, delay=0)
    sleeps = []
    return HttpClient(cfg, FakeSession(responses), sleep=sleeps.append), sleeps


def test_retries_with_exponential_backoff_then_succeeds():
    c, sleeps = client([requests.Timeout("t"), FakeResp(503), FakeResp(200, "ok")])
    assert c.get("http://h.com/") == "ok"
    assert [s for s in sleeps if s] == [1.0, 2.0]
    assert c.retries == 2


def test_gives_up_after_max_retries():
    c, _ = client([requests.ConnectionError("x")] * 3, retries=2)
    with pytest.raises(FetchError):
        c.get("http://h.com/")


def test_404_is_not_retried():
    c, _ = client([FakeResp(404)])
    with pytest.raises(FetchError):
        c.get("http://h.com/")
    assert c.session.calls == 1
