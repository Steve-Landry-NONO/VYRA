import sys
import time
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)
GOOD_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.fixture(autouse=True)
def clear_state(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "STORAGE_DIR", tmp_path)
    with main.state_lock:
        main.inspections.clear()
        main.jobs.clear()
    with main.rate_lock:
        main.rate_history.clear()


@pytest.mark.parametrize("url", [
    "http://www.youtube.com/watch?v=123",
    "https://www.youtube.com.evil.com/watch?v=123",
    "https://127.0.0.1/private",
    "https://youtube.com:8443/watch?v=123",
    "https://user:password@youtube.com/watch?v=123",
    "file:///etc/passwd",
    "https://example.com/something",
    "https://youtube.com/",
    "https://youtube.com/redirect?url=https://example.com/private",
    "https://instagram.com/accounts/login/",
    "https://tiktok.com/redirect?url=https://example.com/private",
])
def test_reject_invalid_hosts(url):
    assert client.post("/api/inspect", json={"url": url}).status_code == 422


def test_accept_listed_hosts():
    assert main.platform_from_url(GOOD_URL) == "YouTube"
    assert main.platform_from_url("https://www.instagram.com/reel/foo/") == "Instagram"
    assert main.platform_from_url("https://vm.tiktok.com/abc/") == "TikTok"
    assert main.platform_from_url("https://t.snapchat.com/foo") == "Snapchat · bêta"


class FakeYoutubeDL:
    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        assert url == GOOD_URL
        assert download is False
        return {
            "id": "abcd",
            "title": "Test de téléchargement",
            "uploader": "Auteur",
            "duration": 85,
            "thumbnail": "https://i.ytimg.com/vi/example/hqdefault.jpg",
            "formats": [
                {"height": 360, "vcodec": "h264", "acodec": "none"},
                {"height": 720, "vcodec": "h264", "acodec": "none"},
                {"height": 1080, "vcodec": "h264", "acodec": "none"},
                {"height": None, "vcodec": "none", "acodec": "aac"},
            ],
        }

    def download(self, urls):
        assert urls == [GOOD_URL]
        assert self.options["js_runtimes"] == {"node": {}}
        path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4" if self.options.get("recodevideo") else "mp3"))
        path.write_bytes(b"fake-media")
        for hook in self.options.get("progress_hooks", []):
            hook({"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000})
            hook({"status": "finished"})


def test_full_download_flow(monkeypatch):
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    inspection = client.post("/api/inspect", json={"url": GOOD_URL})
    assert inspection.status_code == 200, inspection.text
    data = inspection.json()
    assert data["heights"] == [1080, 720, 360]
    assert data["title"] == "Test de téléchargement"
    assert client.post("/api/download", json={"inspection_id": data["inspection_id"], "format": "mp4", "quality": "480"}).status_code == 422
    job_resp = client.post("/api/download", json={"inspection_id": data["inspection_id"], "format": "mp4", "quality": "720"})
    assert job_resp.status_code == 202
    job_id = job_resp.json()["job_id"]
    for _ in range(100):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in {"ready", "error"}:
            break
        time.sleep(.01)
    assert status["status"] == "ready", status
    assert status["progress"] == 100
    file = client.get(status["download_url"])
    assert file.status_code == 200
    assert file.content == b"fake-media"
    assert "attachment" in file.headers["content-disposition"]


def test_mp3_flow(monkeypatch):
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYoutubeDL))
    inspection = client.post("/api/inspect", json={"url": GOOD_URL}).json()
    bad = client.post("/api/download", json={"inspection_id": inspection["inspection_id"], "format": "mp3", "quality": "best"})
    assert bad.status_code == 422
    good = client.post("/api/download", json={"inspection_id": inspection["inspection_id"], "format": "mp3", "quality": "audio"})
    assert good.status_code == 202
    job_id = good.json()["job_id"]
    for _ in range(100):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in {"ready", "error"}:
            break
        time.sleep(.01)
    assert status["status"] == "ready"
    assert client.get(status["download_url"]).headers["content-type"].startswith("audio/mpeg")


def test_expired_inspection():
    response = client.post("/api/download", json={"inspection_id": "a" * 32, "format": "mp4", "quality": "best"})
    assert response.status_code == 410


def test_home_and_health():
    assert client.get("/").status_code == 200
    assert 'Vos vidéos' in client.get("/").text
    assert client.get("/api/health").json()["ok"]


def test_hosted_instance_rejects_without_password_configuration(monkeypatch):
    monkeypatch.setenv("VYRA_REQUIRE_AUTH", "1")
    monkeypatch.delenv("VYRA_ACCESS_PASSWORD", raising=False)
    assert client.get("/").status_code == 503
    assert client.get("/api/health").status_code == 200


def test_hosted_instance_requires_correct_basic_auth(monkeypatch):
    import base64
    monkeypatch.setenv("VYRA_REQUIRE_AUTH", "1")
    monkeypatch.setenv("VYRA_ACCESS_USER", "testeur")
    monkeypatch.setenv("VYRA_ACCESS_PASSWORD", "mot-de-passe-test")
    assert client.get("/").status_code == 401
    assert client.get("/").headers.get("WWW-Authenticate", "").startswith("Basic ")
    invalid = base64.b64encode(b"testeur:errone").decode()
    assert client.get("/api/jobs/aucun", headers={"Authorization": f"Basic {invalid}"}).status_code == 401
    accepted = base64.b64encode(b"testeur:mot-de-passe-test").decode()
    assert client.get("/", headers={"Authorization": f"Basic {accepted}"}).status_code == 200
    assert client.get("/api/jobs/aucun", headers={"Authorization": f"Basic {accepted}"}).status_code == 404


@pytest.mark.parametrize(("error", "category"), [
    ("ERROR: Sign in to confirm you're not a bot", "youtube_bot_check"),
    ("ERROR: This is a private video. Sign in", "login_required"),
    ("ERROR: HTTP Error 403: Forbidden", "access_forbidden"),
    ("ERROR: HTTP Error 429: Too Many Requests", "rate_limited"),
    ("ERROR: No supported JavaScript runtime could be found", "youtube_javascript"),
    ("ERROR: Unsupported URL", "unsupported_url"),
])
def test_failure_categories(error, category):
    assert main.failure_category(RuntimeError(error)) == category


def test_youtube_bot_check_is_not_mislabeled_as_private(monkeypatch, caplog):
    def fail(url):
        raise RuntimeError(f"https://youtube.com/watch?v=SECRET_TOKEN: Sign in to confirm you're not a bot")
    monkeypatch.setattr(main, "metadata_from_url", fail)
    with caplog.at_level("WARNING", logger="vyra.diagnostics"):
        response = client.post("/api/inspect", json={"url": GOOD_URL})
    assert response.status_code == 422
    assert "anti-robot" in response.json()["detail"]
    assert "SECRET_TOKEN" not in caplog.text
    assert "youtube_bot_check" in caplog.text


def test_optional_diagnostic_requires_configuration(monkeypatch):
    monkeypatch.delenv("VYRA_DIAGNOSTIC_URL", raising=False)
    with monkeypatch.context() as m:
        m.setattr(main.executor, "submit", lambda *args: pytest.fail("Should not run"))
        main.start_optional_diagnostic()
