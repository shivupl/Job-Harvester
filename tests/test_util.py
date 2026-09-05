import html
from jobwatch.util import strip_tags, to_utc_iso
from jobwatch.models import Posting


def test_strip_tags_removes_markup_and_unescapes_entities():
    assert strip_tags("<p>Python &amp; Go</p><ul><li>x</li></ul>") == "Python & Go\nx"


def test_greenhouse_order_unescape_then_strip():
    escaped = "&lt;p&gt;We hire &lt;strong&gt;new grads&lt;/strong&gt;&lt;/p&gt;"
    out = strip_tags(html.unescape(escaped))
    assert out == "We hire new grads"
    assert "<" not in out and "&lt;" not in out


def test_to_utc_iso_handles_offsets_z_and_epoch_ms():
    assert to_utc_iso("2026-09-03T13:32:53-04:00") == "2026-09-03T17:32:53+00:00"
    assert to_utc_iso("2026-03-12T16:38:15.322+00:00") == "2026-03-12T16:38:15+00:00"
    assert to_utc_iso("2026-09-01T15:01:17Z") == "2026-09-01T15:01:17+00:00"
    assert to_utc_iso(1711403416463) == "2024-03-25T21:50:16+00:00"
    assert to_utc_iso(None) is None
    assert to_utc_iso("garbage") is None


def test_posting_key():
    p = Posting(ats="ashby", slug="acme", job_id="123", title="t", company="Acme",
                location="", remote=None, description="", posted_at=None, url="")
    assert p.key == "ashby:acme:123"
