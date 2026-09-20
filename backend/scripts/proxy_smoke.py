"""Exercise the running Next -> Django proxy without printing credentials or tokens."""

import http.cookiejar
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    credentials = json.loads(
        (Path(__file__).resolve().parents[1] / ".local/demo-access.json").read_text()
    )
    endpoints = {
        "ADMIN": [
            "students",
            "teachers",
            "parents",
            "batches",
            "timetable",
            "attendance",
            "fees",
            "materials",
            "exams",
            "results",
            "announcements",
            "settings",
            "scope",
        ],
        "TEACHER": [
            "batches",
            "timetable",
            "attendance",
            "materials",
            "exams",
            "results",
            "announcements",
            "scope",
        ],
        "STUDENT": [
            "timetable",
            "attendance",
            "fees",
            "materials",
            "exams",
            "results",
            "announcements",
            "scope",
        ],
        "PARENT": ["students", "attendance", "fees", "exams", "results", "announcements", "scope"],
        "SUPER_ADMIN": [
            "super-admin/institutes",
            "super-admin/domains",
            "super-admin/plans",
            "super-admin/subscriptions",
        ],
    }
    checked = set()
    for item in credentials:
        key = (item["host"], item["role"])
        if key in checked:
            continue
        checked.add(key)
        # Host header tests the same local Next listener, including platform.localhost.
        base = "http://" + ("127.0.0.1" if item["host"] == "127.0.0.1" else "localhost") + ":3000"
        host = item["host"] + ":3000"
        opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def request(path, payload=None, csrf="", host=host, base=base, opener=opener):
            headers = {"Host": host, "Origin": "http://" + host}
            if payload is not None:
                headers.update({"Content-Type": "application/json", "X-CSRFToken": csrf})
            req = Request(
                base + path,
                data=json.dumps(payload).encode() if payload is not None else None,
                headers=headers,
            )
            try:
                with opener.open(req, timeout=30) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                return error.code, {}  # Never log response bodies from authentication errors.

        status, context = request("/api/auth/context/")
        if status != 200:
            raise RuntimeError(f"Context failed: {item['role']}, HTTP {status}")
        status, session = request(
            "/api/auth/login/",
            {"username": item["username"], "password": item["password"]},
            context["csrfToken"],
        )
        if status != 200:
            raise RuntimeError(f"Login failed: {item['role']}, HTTP {status}")
        for endpoint in ["dashboard"] + endpoints[item["role"]]:
            status, _ = request("/api/" + endpoint + "/")
            if status != 200:
                raise RuntimeError(f"{item['role']} endpoint {endpoint}: HTTP {status}")
        status, _ = request("/api/auth/logout/", {}, session["csrfToken"])
        if status != 200:
            raise RuntimeError("Logout failed")
        print(f"PASS: {item['institute']} / {item['role']} proxy login, module reads, logout")


if __name__ == "__main__":
    main()
