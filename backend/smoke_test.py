"""End-to-end smoke test against a running server: captcha -> signup -> login -> search."""

import base64
import re
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def solve_captcha(client: httpx.Client) -> dict[str, str]:
    body = client.get(f"{BASE}/api/auth/captcha").raise_for_status().json()
    svg = base64.b64decode(body["image_data_uri"].split(",", 1)[1]).decode()
    answer = "".join(re.findall(r"<text[^>]*>(.)</text>", svg))
    return {"challenge_id": body["challenge_id"], "answer": answer}


def main() -> int:
    with httpx.Client(timeout=10) as client:
        assert client.get(f"{BASE}/api/health").json()["status"] == "ok"
        print("health ok")

        username = "smoke_user"
        password = "smoke-password-1"
        signup = client.post(
            f"{BASE}/api/auth/signup",
            json={
                "email": f"{username}@example.com",
                "username": username,
                "password": password,
                "captcha": solve_captcha(client),
            },
        )
        if signup.status_code == 409:
            print("signup skipped (user exists)")
        else:
            assert signup.status_code == 201, signup.text
            print("signup ok")

        bad = solve_captcha(client)
        bad["answer"] = "ZZZZZ"
        rejected = client.post(
            f"{BASE}/api/auth/login",
            json={"identifier": username, "password": password, "captcha": bad},
        )
        assert rejected.status_code == 400, rejected.text
        print("bad captcha rejected ok")

        login = client.post(
            f"{BASE}/api/auth/login",
            json={
                "identifier": username,
                "password": password,
                "captcha": solve_captcha(client),
            },
        )
        assert login.status_code == 200, login.text
        tokens = login.json()
        print("login ok")

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me = client.get(f"{BASE}/api/auth/me", headers=headers).raise_for_status().json()
        assert me["username"] == username
        print("me ok")

        results = client.get(
            f"{BASE}/api/resources/search", params={"q": "python"}
        ).raise_for_status().json()
        assert results["total"] >= 1, results
        print(f"search 'python' -> {results['total']} results:")
        for item in results["items"]:
            print(f"   - {item['title']} ({item['url']}) tags={item['tags']}")

        tagged = client.get(
            f"{BASE}/api/resources/search", params={"tag": "security"}
        ).raise_for_status().json()
        print(f"search tag=security -> {tagged['total']} results")

        refreshed = client.post(
            f"{BASE}/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 200, refreshed.text
        print("refresh ok")

    print("\nALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
