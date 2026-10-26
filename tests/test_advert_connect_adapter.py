"""Offline tests for the credential-free Advert Connect status probe."""
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from tyrion import advert_connect_adapter as adapter, bridge

class Response:
    def __init__(self, doc):
        self.body = io.BytesIO(json.dumps(doc).encode())
    def read(self, n=-1):
        return self.body.read(n)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []
    def open(self, request, timeout=0):
        self.requests.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

class AdvertConnectReadOnlyTests(unittest.TestCase):
    def test_authorization_required_is_not_a_native_connection(self):
        exc = urllib.error.HTTPError(
            "https://advertpreneur.com" + adapter.ROUTE, 401,
            "Unauthorized", {}, io.BytesIO(b'{"code":"rest_forbidden"}')
        )
        opener = FakeOpener(exc)
        result = adapter.probe_host("advertpreneur.com", opener=opener)
        self.assertEqual(result["status"], "authentication_required")
        self.assertTrue(result["route_confirmed"])
        self.assertFalse(result["authenticated"])
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 5)
        self.assertEqual(request.full_url, "https://advertpreneur.com" + adapter.ROUTE)
        self.assertNotIn("authorization", str(request.headers).lower())

    def test_public_200_does_not_claim_authentication(self):
        opener = FakeOpener(Response({"ok": True, "plugin": "Advertpreneur Connect", "version": "0.6.3"}))
        result = adapter.probe_host("coocoobabys.com", opener=opener)
        self.assertEqual(result["status"], "public_status_available")
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["plugin_version"], "0.6.3")

    def test_wrong_shape_fails_closed(self):
        result = adapter.probe_host("advertpreneur.com", opener=FakeOpener(Response({"ok": True, "plugin": "Another Plugin"})))
        self.assertEqual(result["status"], "unexpected_public_response")
        self.assertFalse(result["route_confirmed"])

    def test_disallow_arbitrary_hosts_and_urls(self):
        for host in ("localhost", "127.0.0.1", "evil.example", "https://advertpreneur.com", "advertpreneur.com.evil.example"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                adapter.probe_host(host, opener=FakeOpener(Response({})))
        with self.assertRaises(ValueError):
            adapter.probe("evil.example")

    def test_http_redirect_is_not_followed(self):
        redirect = urllib.error.HTTPError(
            "https://advertpreneur.com" + adapter.ROUTE, 302,
            "Moved", {"Location":"http://127.0.0.1:9999/"}, io.BytesIO(b"")
        )
        result = adapter.probe_host("advertpreneur.com", opener=FakeOpener(redirect))
        self.assertEqual(result["status"], "redirect_blocked")
        self.assertFalse(result["authenticated"])
        self.assertIsNone(adapter._NoRedirect().redirect_request(None,None,302,None,{}, "http://127.0.0.1/"))

    def test_oversized_body_fails_closed(self):
        opener = FakeOpener(Response({"text": "x" * 20000}))
        result = adapter.probe_host("advertpreneur.com", opener=opener)
        self.assertEqual(result["status"], "probe_failed")

    def test_bridge_tool_is_nonmutating(self):
        with patch.object(adapter, "probe", return_value={"authenticated":False,"sites":[]}) as mocked:
            self.assertEqual(bridge.call("tyrion_probe_advert_connect", {"site":"all"}), {"authenticated":False,"sites":[]})
            mocked.assert_called_once_with("all")
        self.assertTrue(any(t["name"]=="tyrion_probe_advert_connect" for t in bridge.TOOLS))

if __name__ == "__main__":
    unittest.main()
