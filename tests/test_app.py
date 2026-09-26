from __future__ import annotations

import re
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import unittest
from contextlib import closing
from pathlib import Path

import main


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class ForumHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.original_database_path = main.DATABASE_PATH
        main.DATABASE_PATH = Path(cls.temp_directory.name) / "test-forum.sqlite3"
        main.initialize_database()
        cls.server = main.ForumHTTPServer(("127.0.0.1", 0), main.ForumHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.client = urllib.request.build_opener(NoRedirectHandler())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)
        main.DATABASE_PATH = cls.original_database_path
        cls.temp_directory.cleanup()

    def setUp(self) -> None:
        with closing(sqlite3.connect(main.DATABASE_PATH)) as connection, connection:
            connection.execute("DELETE FROM messages")
            connection.execute("DELETE FROM topics")
            connection.execute("DELETE FROM users")
        main.TOPICS.clear()
        main.SESSIONS.clear()
        main.SESSION_CSRF.clear()
        main.SESSION_EXPIRES.clear()
        main.AUTH_ATTEMPTS.clear()

    def request(
        self,
        path: str,
        fields: dict[str, str] | None = None,
        cookie: str = "",
        raw_body: bytes | None = None,
        content_type: str = "application/x-www-form-urlencoded",
    ) -> tuple[int, object, str]:
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        body = raw_body
        if fields is not None:
            body = urllib.parse.urlencode(fields).encode("utf-8")
        if body is not None:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers)
        try:
            response = self.client.open(request)
        except urllib.error.HTTPError as error:
            response = error
        status = response.code
        headers = response.headers
        content = response.read().decode("utf-8", errors="replace")
        response.close()
        return status, headers, content

    @staticmethod
    def csrf_token(page: str) -> str:
        match = re.search(r'name="csrf_token" value="([^"]+)"', page)
        if match is None:
            raise AssertionError("The page does not contain a CSRF token")
        return match.group(1)

    @staticmethod
    def cookie_header(headers: object) -> str:
        values = headers.get_all("Set-Cookie", [])
        return "; ".join(value.split(";", 1)[0] for value in values)

    def register(self, username: str = "ForumTester") -> str:
        status, headers, page = self.request("/register")
        self.assertEqual(status, 200)
        cookie = self.cookie_header(headers)
        token = self.csrf_token(page)
        status, headers, _ = self.request(
            "/register",
            {"username": username, "password": "correct horse battery staple", "csrf_token": token},
            cookie,
        )
        self.assertEqual(status, 303)
        return self.cookie_header(headers)

    def test_registration_requires_csrf_and_stores_only_password_hash(self) -> None:
        status, headers, page = self.request("/register")
        self.assertEqual(status, 200)
        cookie = self.cookie_header(headers)
        token = self.csrf_token(page)

        status, _, _ = self.request(
            "/register",
            {"username": "NoCsrf", "password": "correct horse battery staple"},
            cookie,
        )
        self.assertEqual(status, 403)
        self.assertIsNone(main.find_member("NoCsrf"))

        status, headers, _ = self.request(
            "/register",
            {"username": "HashCheck", "password": "correct horse battery staple", "csrf_token": token},
            cookie,
        )
        self.assertEqual(status, 303)
        self.assertIn("session=", self.cookie_header(headers))
        self.assertIn("HttpOnly", " ".join(headers.get_all("Set-Cookie", [])))

        with closing(sqlite3.connect(main.DATABASE_PATH)) as connection:
            salt, password_hash = connection.execute(
                "SELECT salt, password_hash FROM users WHERE username_key = ?",
                ("hashcheck",),
            ).fetchone()
        self.assertNotEqual(password_hash, b"correct horse battery staple")
        self.assertEqual(password_hash, main.hash_password("correct horse battery staple", salt))

    def test_topic_creation_requires_csrf_and_renders_sanitized_hashtags(self) -> None:
        cookie = self.register()
        status, _, page = self.request("/", cookie=cookie)
        self.assertEqual(status, 200)
        token = self.csrf_token(page)

        status, _, _ = self.request(
            "/topics",
            {"title": "Forged", "csrf_token": "invalid"},
            cookie,
        )
        self.assertEqual(status, 403)
        self.assertEqual(main.TOPICS, [])

        status, _, _ = self.request(
            "/topics",
            {
                "title": "<script>not markup</script>",
                "category": "Projects",
                "body": "The opening post must be saved too.",
                "hashtags": "#Python, python #web-access #invalid!",
                "csrf_token": token,
            },
            cookie,
        )
        self.assertEqual(status, 303)
        self.assertEqual(main.TOPICS[0]["hashtags"], ["python", "web-access"])
        _, _, page = self.request("/", cookie=cookie)
        self.assertIn("&lt;script&gt;not markup&lt;/script&gt;", page)
        self.assertNotIn("<script>not markup</script>", page)
        self.assertNotIn("{{COUNT_", page)

        topic_id = main.TOPICS[0]["id"]
        main.TOPICS.clear()
        main.load_topics()
        self.assertEqual(main.TOPICS[0]["hashtags"], ["python", "web-access"])
        self.assertEqual(main.TOPICS[0]["messages"][0]["body"], "The opening post must be saved too.")

        status, _, page = self.request(f"/topic/{topic_id}", cookie=cookie)
        token = self.csrf_token(page)
        status, _, _ = self.request(
            f"/topic/{topic_id}/reply",
            {"body": "A reply that should persist.", "csrf_token": token},
            cookie,
        )
        self.assertEqual(status, 303)
        main.TOPICS.clear()
        main.load_topics()
        self.assertEqual(main.TOPICS[0]["replies"], 1)
        self.assertEqual(main.TOPICS[0]["messages"][-1]["body"], "A reply that should persist.")

    def test_logout_requires_csrf_and_expires_both_cookies(self) -> None:
        cookie = self.register("LogoutTester")
        _, _, page = self.request("/", cookie=cookie)
        token = self.csrf_token(page)

        status, headers, _ = self.request("/logout", {"csrf_token": token}, cookie)
        self.assertEqual(status, 303)
        expired_cookies = headers.get_all("Set-Cookie", [])
        self.assertEqual(len(expired_cookies), 2)
        self.assertTrue(all("Max-Age=0" in value for value in expired_cookies))
        self.assertEqual(main.SESSIONS, {})
        self.assertEqual(main.SESSION_CSRF, {})

    def test_security_headers_and_request_limits(self) -> None:
        status, headers, _ = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("style-src-attr 'none'", headers.get("Content-Security-Policy", ""))
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        self.assertTrue(headers.get("Server", "").startswith("CommonGround"))

        status, _, _ = self.request(
            "/login",
            raw_body=b"x" * (main.MAX_REQUEST_BYTES + 1),
        )
        self.assertEqual(status, 413)

        status, _, _ = self.request(
            "/login",
            raw_body=b"x=1",
            content_type="application/x-www-form-urlencoded-evil",
        )
        self.assertEqual(status, 415)

    def test_login_rate_limit(self) -> None:
        main.create_user("RateLimit", "correct horse battery staple")
        status, headers, page = self.request("/login")
        self.assertEqual(status, 200)
        cookie = self.cookie_header(headers)
        token = self.csrf_token(page)

        for _ in range(main.MAX_AUTH_ATTEMPTS):
            status, _, _ = self.request(
                "/login",
                {"username": "RateLimit", "password": "wrong password", "csrf_token": token},
                cookie,
            )
            self.assertEqual(status, 200)
        status, _, _ = self.request(
            "/login",
            {"username": "RateLimit", "password": "wrong password", "csrf_token": token},
            cookie,
        )
        self.assertEqual(status, 429)


class HelperTests(unittest.TestCase):
    def test_hashtag_parser_normalizes_and_limits_tags(self) -> None:
        self.assertEqual(
            main.parse_hashtags("#Python, python #web-access #invalid!"),
            ["python", "web-access"],
        )
        self.assertEqual(len(main.parse_hashtags(" ".join(f"#tag{index}" for index in range(12)))), 8)

    def test_safe_next_path_rejects_external_destinations(self) -> None:
        self.assertEqual(main.safe_next_path("/profile"), "/profile")
        self.assertEqual(main.safe_next_path("//example.com"), "/")
        self.assertEqual(main.safe_next_path("/\\example.com"), "/")


if __name__ == "__main__":
    unittest.main()