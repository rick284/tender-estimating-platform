import io, os, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app  # noqa: E402

client = TestClient(app)
PRIVATE = Path(__file__).resolve().parents[2] / "private" / "Rev34E.xlsx"


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_rejects_non_xlsx_name():
    r = client.post("/api/estimates/import", files={"file": ("a.txt", b"hello")})
    assert r.status_code == 400


def test_rejects_fake_xlsx():
    r = client.post("/api/estimates/import", files={"file": ("a.xlsx", b"not a zip")})
    assert r.status_code == 400


def test_rejects_zip_that_is_not_a_workbook():
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "x")
    r = client.post("/api/estimates/import", files={"file": ("a.xlsx", buf.getvalue())})
    assert r.status_code == 422
    assert "could not be read" in r.json()["detail"]


def test_rejects_other_workbook():
    import openpyxl
    wb = openpyxl.Workbook(); buf = io.BytesIO(); wb.save(buf)
    r = client.post("/api/estimates/import", files={"file": ("a.xlsx", buf.getvalue())})
    assert r.status_code == 422 and "missing sheets" in r.json()["detail"]


def test_demo_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_WORKBOOK", raising=False)
    assert client.get("/api/demo").status_code == 404


@pytest.mark.skipif(not PRIVATE.exists(), reason="private workbook not present")
def test_import_hobsonville():
    r = client.post("/api/estimates/import", files={"file": ("Rev34E.xlsx", PRIVATE.read_bytes())})
    assert r.status_code == 200
    j = r.json()
    assert j["reconciled"] is True and round(j["summary"]["all_in"], 2) == 1226916.81
