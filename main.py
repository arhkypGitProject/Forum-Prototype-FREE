from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import closing
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "forum.sqlite3")))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").casefold() in {"1", "true", "yes"}
PASSWORD_ITERATIONS = 310_000
SESSIONS: dict[str, str] = {}
SESSION_CSRF: dict[str, str] = {}
SESSION_EXPIRES: dict[str, float] = {}
AUTH_ATTEMPTS: dict[str, list[float]] = {}
AUTH_ATTEMPTS_LOCK = threading.Lock()
MAX_REQUEST_BYTES = 64 * 1024
MAX_AUTH_ATTEMPTS = 8
AUTH_WINDOW_SECONDS = 15 * 60
SESSION_MAX_AGE = 8 * 60 * 60
CATEGORIES = ("Discussions", "Projects", "Questions", "Off-topic")
TOPICS: list[dict] = []


def initialize_database() -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "username_key TEXT PRIMARY KEY, username TEXT NOT NULL, "
            "salt BLOB NOT NULL, password_hash BLOB NOT NULL, "
            "bio TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS topics ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "category TEXT NOT NULL, author TEXT NOT NULL, initials TEXT NOT NULL, "
            "time TEXT NOT NULL, replies INTEGER NOT NULL DEFAULT 0, "
            "views INTEGER NOT NULL DEFAULT 0, tag TEXT NOT NULL DEFAULT '', "
            "hashtags TEXT NOT NULL DEFAULT '[]', color TEXT NOT NULL, body TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, "
            "author TEXT NOT NULL, initials TEXT NOT NULL, time TEXT NOT NULL, "
            "body TEXT NOT NULL, color TEXT NOT NULL, "
            "FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "bio" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
        if "created_at" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        connection.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at = ''")
        connection.commit()


def load_topics() -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        topic_rows = connection.execute(
            "SELECT id, title, category, author, initials, time, replies, views, "
            "tag, hashtags, color, body FROM topics ORDER BY id DESC"
        ).fetchall()
        message_rows = connection.execute(
            "SELECT topic_id, author, initials, time, body, color "
            "FROM messages ORDER BY id"
        ).fetchall()
    messages_by_topic: dict[int, list[dict[str, str]]] = {}
    for topic_id, author, initials, message_time, body, color in message_rows:
        messages_by_topic.setdefault(int(topic_id), []).append(
            {"author": author, "initials": initials, "time": message_time, "body": body, "color": color}
        )
    TOPICS.clear()
    for row in topic_rows:
        topic_id = int(row[0])
        TOPICS.append(
            {
                "id": topic_id,
                "title": str(row[1]),
                "category": str(row[2]),
                "author": str(row[3]),
                "initials": str(row[4]),
                "time": str(row[5]),
                "replies": int(row[6]),
                "views": int(row[7]),
                "tag": str(row[8]),
                "hashtags": json.loads(row[9]),
                "color": str(row[10]),
                "body": str(row[11]),
                "messages": messages_by_topic.get(topic_id, []),
            }
        )


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def create_user(username: str, password: str) -> bool:
    salt = secrets.token_bytes(16)
    try:
        with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
            connection.execute(
                "INSERT INTO users (username_key, username, salt, password_hash) VALUES (?, ?, ?, ?)",
                (username.casefold(), username, salt, hash_password(password, salt)),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def authenticate_user(username: str, password: str) -> str | None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        row = connection.execute(
            "SELECT username, salt, password_hash FROM users WHERE username_key = ?",
            (username.strip().casefold(),),
        ).fetchone()
    if row is None or not hmac.compare_digest(hash_password(password, row[1]), row[2]):
        return None
    return str(row[0])


def list_members() -> list[dict[str, str]]:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        rows = connection.execute(
            "SELECT username, bio, created_at FROM users ORDER BY username_key"
        ).fetchall()
    return [
        {"username": str(row[0]), "bio": str(row[1]), "created_at": str(row[2])}
        for row in rows
    ]


def find_member(username: str) -> dict[str, str] | None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        row = connection.execute(
            "SELECT username, bio, created_at FROM users WHERE username_key = ?",
            (username.casefold(),),
        ).fetchone()
    if row is None:
        return None
    return {"username": str(row[0]), "bio": str(row[1]), "created_at": str(row[2])}


def update_member_bio(username: str, bio: str) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            "UPDATE users SET bio = ? WHERE username_key = ?",
            (bio, username.casefold()),
        )


def format_join_date(value: str) -> str:
    try:
        return sqlite3.datetime.datetime.fromisoformat(value).strftime("%B %Y")
    except (AttributeError, TypeError, ValueError):
        return "Community member"


def member_cards(members: list[dict[str, str]]) -> str:
    if not members:
        return '<p class="empty-state">No members yet. Create an account to be the first.</p>'
    cards = []
    for member in members:
        username = member["username"]
        initials = "".join(part[0] for part in username.split()[:2]).upper() or username[:2].upper()
        bio = member["bio"] or "No bio added yet."
        cards.append(
            f'<a class="member-row" href="/profile?user={quote(username, safe="")}">'
            f'<span class="member-avatar">{html.escape(initials)}</span>'
            f'<span class="member-copy"><strong>{html.escape(username)}</strong>'
            f'<span>{html.escape(bio)}</span></span>'
            f'<span class="member-joined">Joined {html.escape(format_join_date(member["created_at"]))}</span></a>'
        )
    return "".join(cards)


def profile_content(member: dict[str, str], is_owner: bool, csrf_token: str, error: str = "") -> str:
    username = member["username"]
    initials = "".join(part[0] for part in username.split()[:2]).upper() or username[:2].upper()
    bio = member["bio"] or "This member has not added a bio yet."
    form = ""
    if is_owner:
        form = (
            f'<form class="profile-editor" method="post" action="/profile">{csrf_input(csrf_token)}{error}'
            '<label for="bio">About you</label>'
            f'<textarea id="bio" name="bio" maxlength="280" placeholder="A few words about you...">{html.escape(member["bio"])}</textarea>'
            '<div class="profile-form-footer"><span>Up to 280 characters</span>'
            '<button class="new-topic" type="submit">Save profile</button></div></form>'
        )
    return (
        '<div class="profile-heading">'
        f'<span class="profile-large-avatar">{html.escape(initials)}</span>'
        f'<div><div class="eyebrow">Community member</div><h1>{html.escape(username)}</h1>'
        f'<p class="profile-joined">Joined {html.escape(format_join_date(member["created_at"]))}</p></div></div>'
        f'<p class="profile-bio">{html.escape(bio)}</p>{form}'
    )


def parse_hashtags(value: str) -> list[str]:
    hashtags = []
    for item in re.split(r"[\s,]+", value):
        hashtag = item.strip().removeprefix("#").casefold()
        if re.fullmatch(r"[\w-]{1,32}", hashtag) and hashtag not in hashtags:
            hashtags.append(hashtag)
        if len(hashtags) == 8:
            break
    return hashtags


def render_hashtags(topic: dict, linked: bool = True) -> str:
    hashtags = topic.get("hashtags", [])
    if not hashtags:
        return ""
    if linked:
        items = (
            f'<a class="hashtag" href="/?tag={quote(hashtag, safe="")}">#{html.escape(hashtag)}</a>'
            for hashtag in hashtags
        )
    else:
        items = (f'<span class="hashtag">#{html.escape(hashtag)}</span>' for hashtag in hashtags)
    return f'<div class="topic-hashtags">{"".join(items)}</div>'


def topic_card(topic: dict) -> str:
    tag = f'<span class="tag">{html.escape(topic["tag"])}</span>' if topic["tag"] else ""
    return (
        f'<article class="topic" data-category="{html.escape(topic["category"])}" '
        f'data-tag="{html.escape(topic["tag"])}"><div><h3 class="topic-title">'
        f'<a class="topic-link" href="/topic/{topic["id"]}">{html.escape(topic["title"])}{tag}</a></h3><div class="topic-meta">'
        f'<span class="mini-avatar {topic["color"]}">{html.escape(topic["initials"])}</span>'
        f'<span>{html.escape(topic["author"])}</span><span>·</span>'
        f'<span>{html.escape(topic["time"])}</span></div>{render_hashtags(topic)}</div><div class="topic-stats">'
        f'<div><strong>{topic["replies"]}</strong>replies</div>'
        f'<div><strong>{topic["views"]}</strong>views</div></div></article>'
    )


def topic_counts() -> dict[str, int]:
    counts = {"All topics": len(TOPICS)}
    counts.update({category: sum(topic["category"] == category for topic in TOPICS) for category in CATEGORIES})
    return counts


def render_template(name: str, replacements: dict[str, str]) -> bytes:
    template = (BASE_DIR / "templates" / name).read_text(encoding="utf-8")
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template.encode("utf-8")


def user_from_request(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return None
    morsel = cookie.get("session")
    if not morsel:
        return None
    session_id = morsel.value
    if SESSION_EXPIRES.get(session_id, 0) <= time.monotonic():
        SESSIONS.pop(session_id, None)
        SESSION_CSRF.pop(session_id, None)
        SESSION_EXPIRES.pop(session_id, None)
        return None
    return SESSIONS.get(session_id)


def session_id_from_request(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return None
    morsel = cookie.get("session")
    return morsel.value if morsel else None


def csrf_token_for(handler: BaseHTTPRequestHandler) -> str:
    session_id = session_id_from_request(handler)
    if session_id and session_id in SESSIONS:
        return SESSION_CSRF.setdefault(session_id, secrets.token_urlsafe(32))
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return secrets.token_urlsafe(32)
    morsel = cookie.get("csrf")
    return morsel.value if morsel else secrets.token_urlsafe(32)


def csrf_input(token: str) -> str:
    return f'<input type="hidden" name="csrf_token" value="{html.escape(token, quote=True)}">'


def secure_cookie_attribute() -> str:
    return "; Secure" if COOKIE_SECURE else ""


def csrf_cookie(token: str) -> str:
    return f"csrf={token}; Path=/; SameSite=Strict; HttpOnly; Max-Age={SESSION_MAX_AGE}{secure_cookie_attribute()}"


def valid_csrf(handler: BaseHTTPRequestHandler, form: dict[str, list[str]]) -> bool:
    supplied_token = form.get("csrf_token", [""])[0]
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return False
    csrf_morsel = cookie.get("csrf")
    if not csrf_morsel or not supplied_token:
        return False
    if not hmac.compare_digest(csrf_morsel.value, supplied_token):
        return False
    user_from_request(handler)
    session_id = session_id_from_request(handler)
    if session_id and session_id in SESSIONS:
        expected_token = SESSION_CSRF.get(session_id, "")
        return bool(expected_token) and hmac.compare_digest(expected_token, supplied_token)
    return True


def safe_next_path(value: str) -> str:
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or any(ord(char) < 32 for char in value):
        return "/"
    return value


def send_page(handler: BaseHTTPRequestHandler, body: bytes, cookie: str | None = None) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()
    handler.wfile.write(body)


def send_redirect(handler: BaseHTTPRequestHandler, location: str, cookie: str | None = None, csrf: str | None = None) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    if csrf:
        handler.send_header("Set-Cookie", csrf)
    handler.end_headers()


def session_cookie(session_id: str) -> str:
    return f"session={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_MAX_AGE}{secure_cookie_attribute()}"


def account_controls(username: str | None, csrf_token: str = "") -> str:
    if username:
        return (
            f'<a class="profile-name" href="/profile">{html.escape(username)}</a>'
            f'<form class="logout-form" method="post" action="/logout">{csrf_input(csrf_token)}'
            '<button class="register-link" type="submit">Log out</button></form>'
            '<span class="avatar">'
            f'{html.escape(username[:2].upper())}</span>'
        )
    return '<a class="register-link" href="/login">Log in</a><a class="register-link" href="/register">Sign up</a>'


def page_template(username: str | None, csrf_token: str = "") -> bytes:
    create_button = (
        '<button class="new-topic" id="open-modal" type="button">+ New topic</button>'
        if username
        else '<a class="new-topic" href="/login?next=%2F">Log in to post</a>'
    )
    modal = (
        '<div class="modal-backdrop" id="modal"><form class="modal" method="post" action="/topics">'
        '<h2>Start a conversation</h2><label for="title">Title</label>'
        f'{csrf_input(csrf_token)}<input id="title" name="title" maxlength="160" required placeholder="What would you like to discuss?">'
        '<label for="category">Category</label><select id="category" name="category">'
        + "".join(f"<option>{category}</option>" for category in CATEGORIES)
        + '</select><label for="body">First message</label>'
        '<textarea id="body" name="body" placeholder="Add a little context..."></textarea>'
        '<label for="hashtags">Hashtags</label><input id="hashtags" name="hashtags" maxlength="300" '
        'placeholder="#design #feedback"><span class="field-hint">Separate up to 8 hashtags with spaces or commas.</span>'
        '<div class="modal-actions"><button type="button" class="cancel" id="close-modal">Cancel</button>'
        '<button class="new-topic" type="submit">Publish</button></div></form></div>'
        if username
        else ""
    )
    return render_template(
        "index.html",
        {
            "{{TOPICS}}": "".join(topic_card(topic) for topic in TOPICS),
            **{f"{{{{COUNT_{category.upper().replace('-', '_').replace(' ', '_')}}}}}": str(count) for category, count in topic_counts().items()},
            "{{ACCOUNT_CONTROLS}}": account_controls(username, csrf_token),
            "{{NEW_TOPIC_BUTTON}}": create_button,
            "{{TOPIC_MODAL}}": modal,
        },
    )


def message_cards(topic: dict) -> str:
    return "".join(
        f'<article class="message"><div class="message-author"><span class="mini-avatar {html.escape(message["color"])}">{html.escape(message["initials"])}</span><strong>{html.escape(message["author"])}</strong><span>{html.escape(message["time"])}</span></div><p>{html.escape(message["body"])}</p></article>'
        for message in topic["messages"]
    )


def find_topic(topic_id: int) -> dict | None:
    return next((topic for topic in TOPICS if topic["id"] == topic_id), None)


def create_topic(title: str, category: str, author: str, body: str, hashtags: list[str]) -> dict:
    initials = "".join(part[0] for part in author.split()[:2]).upper() or author[:2].upper()
    topic_time = "just now"
    messages = (
        [{"author": author, "initials": initials, "time": topic_time, "body": body, "color": "coral"}]
        if body
        else []
    )
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO topics (title, category, author, initials, time, tag, hashtags, color, body) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, category, author, initials, topic_time, "New", json.dumps(hashtags), "coral", body),
        )
        topic_id = int(cursor.lastrowid)
        if body:
            connection.execute(
                "INSERT INTO messages (topic_id, author, initials, time, body, color) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (topic_id, author, initials, topic_time, body, "coral"),
            )
    topic = {
        "id": topic_id,
        "title": title,
        "category": category,
        "author": author,
        "initials": initials,
        "time": topic_time,
        "replies": 0,
        "views": 0,
        "tag": "New",
        "hashtags": hashtags,
        "color": "coral",
        "body": body,
        "messages": messages,
    }
    TOPICS.insert(0, topic)
    return topic


def create_reply(topic: dict, author: str, body: str) -> dict[str, str]:
    initials = "".join(part[0] for part in author.split()[:2]).upper() or author[:2].upper()
    message = {"author": author, "initials": initials, "time": "just now", "body": body, "color": "coral"}
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute(
            "INSERT INTO messages (topic_id, author, initials, time, body, color) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (topic["id"], author, initials, message["time"], body, message["color"]),
        )
        connection.execute("UPDATE topics SET replies = replies + 1 WHERE id = ?", (topic["id"],))
    topic["messages"].append(message)
    topic["replies"] += 1
    return message


class ForumHandler(BaseHTTPRequestHandler):
    server_version = "CommonGround"
    sys_version = ""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-DNS-Prefetch-Control", "off")
        self.send_header("X-Permitted-Cross-Domain-Policies", "none")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if COOKIE_SECURE:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "style-src-attr 'none'; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
        )
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def read_form(self) -> dict[str, list[str]] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return None
        if length < 0:
            self.send_error(400, "Invalid Content-Length")
            return None
        if length > MAX_REQUEST_BYTES:
            self.send_error(413, "Request body too large")
            return None
        content_type = self.headers.get("Content-Type", "").partition(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            self.send_error(415, "Unsupported Content-Type")
            return None
        try:
            body = self.rfile.read(length).decode("utf-8")
            return parse_qs(body, max_num_fields=100)
        except (UnicodeDecodeError, ValueError):
            self.send_error(400, "Invalid form data")
            return None

    def reserve_auth_attempt(self) -> bool:
        client_ip = self.client_address[0]
        now = time.monotonic()
        with AUTH_ATTEMPTS_LOCK:
            recent = [
                attempt
                for attempt in AUTH_ATTEMPTS.get(client_ip, [])
                if now - attempt < AUTH_WINDOW_SECONDS
            ]
            if len(recent) >= MAX_AUTH_ATTEMPTS:
                AUTH_ATTEMPTS[client_ip] = recent
                return False
            if len(AUTH_ATTEMPTS) >= 4096:
                stale_clients = [
                    address
                    for address, attempts in AUTH_ATTEMPTS.items()
                    if not any(now - attempt < AUTH_WINDOW_SECONDS for attempt in attempts)
                ]
                for address in stale_clients:
                    AUTH_ATTEMPTS.pop(address, None)
                if client_ip not in AUTH_ATTEMPTS and len(AUTH_ATTEMPTS) >= 4096:
                    return False
            AUTH_ATTEMPTS[client_ip] = [*recent, now]
            return True

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        request_path = parsed_url.path
        current_user = user_from_request(self)
        csrf_token = csrf_token_for(self) if current_user else ""
        if request_path == "/":
            csrf_token = csrf_token_for(self)
            csrf_value = csrf_cookie(csrf_token) if current_user else None
            send_page(self, page_template(current_user, csrf_token), csrf_value)
            return
        if request_path in ("/login", "/register"):
            if current_user:
                send_redirect(self, "/")
                return
            is_login = request_path == "/login"
            template = "login.html" if is_login else "register.html"
            next_path = safe_next_path(parse_qs(parsed_url.query).get("next", ["/"])[0])
            csrf_token = csrf_token_for(self)
            send_page(self, render_template(template, {"{{ERROR}}": "", "{{USER}}": "", "{{NEXT}}": html.escape(next_path, quote=True), "{{CSRF}}": csrf_input(csrf_token)}), csrf_cookie(csrf_token))
            return
        if request_path == "/about":
            send_page(self, render_template("about.html", {"{{ACCOUNT_CONTROLS}}": account_controls(current_user, csrf_token)}), csrf_cookie(csrf_token) if current_user else None)
            return
        if request_path == "/members":
            members = list_members()
            send_page(self, render_template("members.html", {
                "{{ACCOUNT_CONTROLS}}": account_controls(current_user, csrf_token),
                "{{MEMBER_COUNT}}": str(len(members)),
                "{{MEMBER_LABEL}}": "member" if len(members) == 1 else "members",
                "{{MEMBERS}}": member_cards(members),
            }))
            return
        if request_path == "/profile":
            requested_user = parse_qs(parsed_url.query).get("user", [""])[0].strip()
            if not requested_user:
                if not current_user:
                    send_redirect(self, "/login?next=%2Fprofile")
                    return
                requested_user = current_user
            member = find_member(requested_user)
            if member is None:
                self.send_error(404)
                return
            is_owner = bool(current_user and current_user.casefold() == member["username"].casefold())
            csrf_token = csrf_token_for(self) if is_owner else ""
            send_page(self, render_template("profile.html", {
                "{{ACCOUNT_CONTROLS}}": account_controls(current_user, csrf_token),
                "{{PROFILE_CONTENT}}": profile_content(member, is_owner, csrf_token),
            }), csrf_cookie(csrf_token) if is_owner else None)
            return
        if request_path.startswith("/topic/"):
            try:
                topic = find_topic(int(request_path.rsplit("/", 1)[1]))
            except ValueError:
                topic = None
            if topic is None:
                self.send_error(404)
                return
            csrf_token = csrf_token_for(self) if current_user else ""
            if current_user:
                reply_form = (
                    f'<form class="reply-form" method="post" action="/topic/{topic["id"]}/reply">{csrf_input(csrf_token)}'
                    '<label for="reply">Your reply</label><textarea id="reply" name="body" required '
                    'placeholder="Write a message..."></textarea><button class="new-topic" type="submit">Post reply</button></form>'
                )
            else:
                reply_form = (
                    '<div class="login-note">To join the conversation, '
                    f'<a href="/login?next=%2Ftopic%2F{topic["id"]}">log in</a> or '
                    '<a href="/register">create an account</a>.</div>'
                )
            send_page(self, render_template("topic.html", {"{{TITLE}}": html.escape(topic["title"]), "{{CATEGORY}}": html.escape(topic["category"]), "{{ACCOUNT_CONTROLS}}": account_controls(current_user, csrf_token), "{{HASHTAGS}}": render_hashtags(topic), "{{MESSAGES}}": message_cards(topic), "{{REPLY_FORM}}": reply_form}), csrf_cookie(csrf_token) if current_user else None)
            return
        if request_path == "/static/style.css":
            self.send_file(BASE_DIR / "static" / "style.css", "text/css; charset=utf-8")
            return
        if request_path == "/static/app.js":
            self.send_file(BASE_DIR / "static" / "app.js", "text/javascript; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        request_path = urlparse(self.path).path
        form = self.read_form()
        if form is None:
            return
        if not valid_csrf(self, form):
            self.send_error(403, "Invalid or missing CSRF token")
            return
        if request_path in ("/register", "/login"):
            if not self.reserve_auth_attempt():
                self.send_error(429, "Too many authentication attempts")
                return
            username = form.get("username", [""])[0].strip()
            password = form.get("password", [""])[0]
            next_path = safe_next_path(form.get("next", ["/"])[0])
            is_register = request_path == "/register"
            if is_register:
                if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username) or not 8 <= len(password) <= 1024:
                    error = "Use a 3–32 character username (letters, numbers, . _ -) and a password between 8 and 1024 characters."
                elif not create_user(username, password):
                    error = "That username is already taken."
                else:
                    error = ""
                authenticated_user = username if not error else None
            else:
                authenticated_user = authenticate_user(username, password) if len(username) <= 32 and len(password) <= 1024 else None
                error = "Invalid username or password." if authenticated_user is None else ""
            if error:
                template = "register.html" if is_register else "login.html"
                csrf_token = csrf_token_for(self)
                send_page(self, render_template(template, {"{{ERROR}}": f'<div class="error">{html.escape(error)}</div>', "{{USER}}": html.escape(username), "{{NEXT}}": html.escape(next_path, quote=True), "{{CSRF}}": csrf_input(csrf_token)}), csrf_cookie(csrf_token))
                return
            session_id = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            SESSIONS[session_id] = str(authenticated_user)
            SESSION_CSRF[session_id] = csrf_token
            SESSION_EXPIRES[session_id] = time.monotonic() + SESSION_MAX_AGE
            with AUTH_ATTEMPTS_LOCK:
                AUTH_ATTEMPTS.pop(self.client_address[0], None)
            send_redirect(self, next_path, session_cookie(session_id), csrf_cookie(csrf_token))
            return
        if request_path == "/logout":
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except CookieError:
                pass
            morsel = cookie.get("session")
            if morsel:
                SESSIONS.pop(morsel.value, None)
                SESSION_CSRF.pop(morsel.value, None)
                SESSION_EXPIRES.pop(morsel.value, None)
            send_redirect(
                self,
                "/",
                f"session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure_cookie_attribute()}",
                f"csrf=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0{secure_cookie_attribute()}",
            )
            return
        if request_path == "/profile":
            current_user = user_from_request(self)
            if not current_user:
                send_redirect(self, "/login?next=%2Fprofile")
                return
            bio = form.get("bio", [""])[0].strip()
            member = find_member(current_user)
            if member is None:
                self.send_error(404)
                return
            if len(bio) > 280:
                error = '<div class="error">Your bio must be 280 characters or fewer.</div>'
                send_page(self, render_template("profile.html", {
                    "{{ACCOUNT_CONTROLS}}": account_controls(current_user, csrf_token_for(self)),
                    "{{PROFILE_CONTENT}}": profile_content(member, True, csrf_token_for(self), error),
                }), csrf_cookie(csrf_token_for(self)))
                return
            update_member_bio(current_user, bio)
            send_redirect(self, "/profile")
            return
        current_user = user_from_request(self)
        if request_path.startswith("/topic/") and request_path.endswith("/reply"):
            if not current_user:
                send_redirect(self, "/login")
                return
            try:
                topic = find_topic(int(request_path.split("/")[2]))
            except (ValueError, IndexError):
                topic = None
            if topic is None:
                self.send_error(404)
                return
            body = form.get("body", [""])[0].strip()
            if len(body) > 10_000:
                self.send_error(413, "Reply is too long")
                return
            if body:
                create_reply(topic, current_user, body)
            send_redirect(self, f"/topic/{topic['id']}")
            return
        if request_path != "/topics":
            self.send_error(404)
            return
        if not current_user:
            send_redirect(self, "/login?next=%2F")
            return
        title = form.get("title", [""])[0].strip()
        category = form.get("category", ["Discussions"])[0]
        hashtags = parse_hashtags(form.get("hashtags", [""])[0])
        body = form.get("body", [""])[0].strip()
        if len(title) > 160 or len(body) > 10_000 or len(form.get("hashtags", [""])[0]) > 300:
            self.send_error(413, "Topic fields are too long")
            return
        if title and category in CATEGORIES:
            create_topic(title, category, current_user, body, hashtags)
        send_redirect(self, "/")

    def log_message(self, format: str, *args: object) -> None:
        return


class ForumHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32
    max_workers = 64

    def __init__(self, server_address: tuple[str, int], request_handler: type[BaseHTTPRequestHandler]) -> None:
        self.worker_slots = threading.BoundedSemaphore(self.max_workers)
        super().__init__(server_address, request_handler)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        if not self.worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.worker_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.worker_slots.release()


if __name__ == "__main__":
    initialize_database()
    load_topics()
    server = ForumHTTPServer((HOST, PORT), ForumHandler)
    print(f"Forum running on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.server_close()
