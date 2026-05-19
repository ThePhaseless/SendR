from config import settings
from models import ScanStatus
from virus_scanner import scan_upload_result


class _FakeUnixClient:
    def __init__(self) -> None:
        self.scanned_path: str | None = None

    def scan(self, path: str):
        self.scanned_path = path
        return {path: ("OK", None)}


class _FakeNetworkClient:
    def __init__(self) -> None:
        self.streamed_payload: bytes | None = None

    def instream(self, stream):
        self.streamed_payload = stream.read()
        return {"stream": ("OK", None)}


def test_scan_upload_result_uses_local_path_for_unix_socket(monkeypatch, tmp_path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"safe")
    fake_client = _FakeUnixClient()

    def _fake_unix_socket(**kwargs) -> _FakeUnixClient:
        assert kwargs["path"] == "/var/run/clamav-test.sock"
        return fake_client

    monkeypatch.setattr(settings, "VIRUS_SCANNING_ENABLED", True)
    monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", "/var/run/clamav-test.sock")
    monkeypatch.setattr("virus_scanner.clamd.ClamdUnixSocket", _fake_unix_socket)

    scan_status, signature = scan_upload_result(target)

    assert scan_status == ScanStatus.clean
    assert signature is None
    assert fake_client.scanned_path == str(target)


def test_scan_upload_result_streams_file_for_network_clamd(monkeypatch, tmp_path):
    target = tmp_path / "sample.txt"
    target.write_bytes(b"safe")
    fake_client = _FakeNetworkClient()

    def _fake_network_socket(**kwargs) -> _FakeNetworkClient:
        assert kwargs["host"] == "sendr-clamav"
        assert kwargs["port"] == 3310
        return fake_client

    monkeypatch.setattr(settings, "VIRUS_SCANNING_ENABLED", True)
    monkeypatch.setattr(settings, "CLAMAV_UNIX_SOCKET", "")
    monkeypatch.setattr(settings, "CLAMAV_HOST", "sendr-clamav")
    monkeypatch.setattr(settings, "CLAMAV_PORT", 3310)
    monkeypatch.setattr(
        "virus_scanner.clamd.ClamdNetworkSocket",
        _fake_network_socket,
    )

    scan_status, signature = scan_upload_result(target)

    assert scan_status == ScanStatus.clean
    assert signature is None
    assert fake_client.streamed_payload == b"safe"
