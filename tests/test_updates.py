import unittest

import requests

from ptz_joystick import updates


class FakeResponse:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code, self.data, self.bad_json = status, data, bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self.bad_json:
            raise requests.JSONDecodeError("bad", "", 0)
        return self.data


class FakeGet:
    """Stands in for requests.get: returns `response` or raises `error`, and records each URL asked for."""

    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
        self.calls: list[str] = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.response


def release(tag):
    return FakeResponse(data={"tag_name": tag, "html_url": f"https://example/{tag}"})


class ParseTest(unittest.TestCase):
    def test_versions(self):
        for tag, want in [("v0.3.0", (0, 3, 0)), ("0.3.0", (0, 3, 0)), ("v1.10.2", (1, 10, 2)),
                          ("dev", None), ("main", None), ("v1.2", None), ("v1.2.3-rc1", None), (None, None)]:
            with self.subTest(tag=tag):
                self.assertEqual(updates.parse(tag), want)


class NewerReleaseTest(unittest.TestCase):
    def test_newer_found(self):
        self.assertEqual(updates.newer_release("v0.2.0", FakeGet(release("v0.10.0"))),
                         ("v0.10.0", "https://example/v0.10.0"))   # numeric, not text, comparison

    def test_same_or_older_is_none(self):
        for tag in ("v0.2.0", "v0.1.9"):
            with self.subTest(tag=tag):
                self.assertIsNone(updates.newer_release("v0.2.0", FakeGet(release(tag))))

    def test_dev_never_asks(self):
        get = FakeGet(release("v9.9.9"))
        self.assertIsNone(updates.newer_release("dev", get))
        self.assertEqual(get.calls, [])

    def test_any_failure_is_none_not_exception(self):
        for name, get in [
            ("timeout", FakeGet(error=requests.Timeout("slow"))),
            ("offline", FakeGet(error=requests.ConnectionError("no network"))),
            ("rate limited", FakeGet(FakeResponse(403))),
            ("bad json", FakeGet(FakeResponse(bad_json=True))),
            ("no tag", FakeGet(FakeResponse(data={"message": "Not Found"}))),
            ("list", FakeGet(FakeResponse(data=[]))),
            ("odd tag", FakeGet(release("nightly"))),
        ]:
            with self.subTest(name), self.assertNoLogs("ptz_joystick.updates", "INFO"):
                self.assertIsNone(updates.newer_release("v0.2.0", get))


class BackgroundTest(unittest.TestCase):
    def test_logs_update_line(self):
        with self.assertLogs("ptz_joystick.updates", "INFO") as logs:
            updates.check_in_background("v0.2.0", FakeGet(release("v0.3.0"))).join(5)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Update available: v0.3.0 (you have v0.2.0) https://example/v0.3.0", logs.output[0])

    def test_silent_when_current(self):
        with self.assertNoLogs("ptz_joystick.updates", "INFO"):
            updates.check_in_background("v0.3.0", FakeGet(release("v0.3.0"))).join(5)


if __name__ == "__main__":
    unittest.main()
