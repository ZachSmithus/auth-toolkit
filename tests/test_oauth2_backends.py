import json

import pytest
from django.test import RequestFactory, TestCase

from oauth2_provider.backends import get_oauthlib_core
from oauth2_provider.models import redirect_to_uri_allowed
from oauth2_provider.oauth2_backends import JSONOAuthLibCore, OAuthLibCore


try:
    from unittest import mock
except ImportError:
    import mock


@pytest.mark.usefixtures("oauth2_settings")
class TestOAuthLibCoreBackend(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.oauthlib_core = OAuthLibCore()

    def test_swappable_server_class(self):
        self.oauth2_settings.OAUTH2_SERVER_CLASS = mock.MagicMock
        oauthlib_core = OAuthLibCore()
        self.assertTrue(isinstance(oauthlib_core.server, mock.MagicMock))

    def test_form_urlencoded_extract_params(self):
        payload = "grant_type=password&username=john&password=123456"
        request = self.factory.post("/o/token/", payload, content_type="application/x-www-form-urlencoded")

        uri, http_method, body, headers = self.oauthlib_core._extract_params(request)
        self.assertIn("grant_type=password", body)
        self.assertIn("username=john", body)
        self.assertIn("password=123456", body)

    def test_application_json_extract_params(self):
        payload = json.dumps(
            {
                "grant_type": "password",
                "username": "john",
                "password": "123456",
            }
        )
        request = self.factory.post("/o/token/", payload, content_type="application/json")

        uri, http_method, body, headers = self.oauthlib_core._extract_params(request)
        self.assertNotIn("grant_type=password", body)
        self.assertNotIn("username=john", body)
        self.assertNotIn("password=123456", body)


class TestCustomOAuthLibCoreBackend(TestCase):
    """
    Tests that the public API behaves as expected when we override
    the OAuthLibCoreBackend core methods.
    """

    class MyOAuthLibCore(OAuthLibCore):
        def _get_extra_credentials(self, request):
            return 1

    def setUp(self):
        self.factory = RequestFactory()

    def test_create_token_response_gets_extra_credentials(self):
        """
        Make sures that extra_credentials parameter is passed to oauthlib
        """
        payload = "grant_type=password&username=john&password=123456"
        request = self.factory.post("/o/token/", payload, content_type="application/x-www-form-urlencoded")

        with mock.patch("oauthlib.oauth2.Server.create_token_response") as create_token_response:
            mocked = mock.MagicMock()
            create_token_response.return_value = mocked, mocked, mocked
            core = self.MyOAuthLibCore()
            core.create_token_response(request)
            self.assertTrue(create_token_response.call_args[0][4] == 1)


class TestJSONOAuthLibCoreBackend(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.oauthlib_core = JSONOAuthLibCore()

    def test_application_json_extract_params(self):
        payload = json.dumps(
            {
                "grant_type": "password",
                "username": "john",
                "password": "123456",
            }
        )
        request = self.factory.post("/o/token/", payload, content_type="application/json")

        uri, http_method, body, headers = self.oauthlib_core._extract_params(request)
        self.assertIn("grant_type=password", body)
        self.assertIn("username=john", body)
        self.assertIn("password=123456", body)


class TestOAuthLibCore(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_validate_authorization_request_unsafe_query(self):
        auth_headers = {
            "HTTP_AUTHORIZATION": "Bearer " + "a_casual_token",
        }
        request = self.factory.get("/fake-resource?next=/fake", **auth_headers)

        oauthlib_core = get_oauthlib_core()
        oauthlib_core.verify_request(request, scopes=[])


@pytest.mark.parametrize(
    "uri, expected_result",
    # localhost is _not_ a loopback URI
    [
        ("http://localhost:3456", False),
        # only http scheme is supported for loopback URIs
        ("https://127.0.0.1:3456", False),
        ("http://127.0.0.1:3456", True),
        ("http://[::1]", True),
        ("http://[::1]:34", True),
    ],
)
def test_uri_loopback_redirect_check(uri, expected_result):
    allowed_uris = ["http://127.0.0.1", "http://[::1]"]
    if expected_result:
        assert redirect_to_uri_allowed(uri, allowed_uris)
    else:
        assert not redirect_to_uri_allowed(uri, allowed_uris)
