import os
import json
import requests
import subprocess

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"


# ─────────────────────────────────────
# UTIL
# ─────────────────────────────────────
def ok():
    print("✅ PASS")


def fail(msg="FAILED"):
    print(f"❌ {msg}")


# ─────────────────────────────────────
# 1. FASTAPI
# ─────────────────────────────────────
def test_fastapi():

    print("\n1. TESTING FASTAPI")

    try:

        response = requests.get(
            f"{BASE_URL}/"
        )

        if response.status_code == 200:
            ok()
        else:
            fail(
                f"Status {response.status_code}"
            )

    except Exception as e:
        fail(str(e))


# ─────────────────────────────────────
# 2. DOCKER
# ─────────────────────────────────────
def test_docker():

    print("\n2. TESTING DOCKER")

    try:

        result = subprocess.run(

            ["docker", "ps"],

            capture_output=True,

            text=True,

        )

        if result.returncode == 0:

            print(result.stdout)

            ok()

        else:

            fail(result.stderr)

    except Exception as e:

        fail(str(e))


# ─────────────────────────────────────
# 3. ENV VARIABLES
# ─────────────────────────────────────
def test_env():

    print("\n3. TESTING ENV VARIABLES")

    required = [

        "GEMINI_API_KEY",

        "DATABASE_URL",

    ]

    missing = []

    for key in required:

        if not os.getenv(key):

            missing.append(key)

    if missing:

        fail(
            f"Missing: {missing}"
        )

    else:

        ok()


# ─────────────────────────────────────
# 4. POSTGRESQL
# ─────────────────────────────────────
def test_postgres():

    print("\n4. TESTING POSTGRESQL")

    try:

        import psycopg2

        conn = psycopg2.connect(
            os.getenv("DATABASE_URL")
        )

        conn.close()

        ok()

    except Exception as e:

        fail(str(e))


# ─────────────────────────────────────
# 5. REDIS
# ─────────────────────────────────────
def test_redis():

    print("\n5. TESTING REDIS")

    try:

        import redis

        r = redis.Redis(
            host="localhost",
            port=6379,
            db=0
        )

        r.ping()

        ok()

    except Exception as e:

        fail(str(e))


# ─────────────────────────────────────
# 6. API ROUTES
# ─────────────────────────────────────
def test_routes():

    print("\n6. TESTING API ROUTES")

    routes = [

        "/",

        "/audit/",

        "/health",

    ]

    for route in routes:

        try:

            response = requests.get(
                f"{BASE_URL}{route}"
            )

            print(
                route,
                "→",
                response.status_code
            )

        except Exception as e:

            fail(f"{route}: {e}")

    ok()


# ─────────────────────────────────────
# 7. REAL AUDIT
# ─────────────────────────────────────
def test_real_audit():

    print("\n7. TESTING REAL AUDIT")

    payload = {

        "url":
        "https://gymshark.com",

        "category":
        "Fashion & Apparel",

        "store_age":
        "Established (1–3 years)",

        "traffic":
        "5,000 – 50,000 visitors",

        "challenge":
        "Getting more traffic",

        "ai_optimization":
        "No, but I want to",

        "merchant_description":
        """
        Ecommerce fitness apparel store
        focused on gymwear and AI visibility.
        """,
    }

    try:

        response = requests.post(

            f"{BASE_URL}/audit/",

            json=payload,

        )

        print(
            "Status:",
            response.status_code
        )

        data = response.json()

        print(
            json.dumps(
                data,
                indent=2
            )[:1000]
        )

        ok()

    except Exception as e:

        fail(str(e))


# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
if __name__ == "__main__":

    print("\n========================")
    print("AI VISIBILITY TEST SUITE")
    print("========================")

    test_fastapi()

    test_docker()

    test_env()

    test_postgres()

    test_redis()

    test_routes()

    test_real_audit()

    print("\n✅ ALL TESTS FINISHED\n")