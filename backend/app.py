from flask import Flask, render_template, jsonify
from flask_cors import CORS
import asyncio
import schedule
import time
import threading
import os
import re
from playwright.async_api import async_playwright

app = Flask(__name__)
CORS(app)

# ================= CONFIG =================
TARGET_USERNAME = "bipo.wq"  # SEM @
MS_TOKEN = os.getenv("TIKTOK_MS_TOKEN")

DATA = {
    "followers": 0,
    "following": 0,
    "likes": 0,
    "videos": 0,
    "is_live": False,
    "last_update": ""
}
# =========================================


def parse_number(text: str) -> int:
    """Converte 1.2K / 3M / 1234 para int"""
    if not text:
        return 0

    text = text.lower().replace(",", "").strip()

    try:
        if "k" in text:
            return int(float(text.replace("k", "")) * 1_000)
        if "m" in text:
            return int(float(text.replace("m", "")) * 1_000_000)
        return int(re.sub(r"\D", "", text))
    except:
        return 0


async def fetch_user_data():
    global DATA

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Cookie": f"msToken={MS_TOKEN};" if MS_TOKEN else ""
            }
        )

        page = await context.new_page()
        await page.goto(f"https://www.tiktok.com/@{TARGET_USERNAME}", timeout=60000)
        await page.wait_for_timeout(5000)

        stats = await page.evaluate("""
        () => {
            const get = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.innerText : null;
            };

            return {
                followers: get('[data-e2e="followers-count"]'),
                following: get('[data-e2e="following-count"]'),
                likes: get('[data-e2e="likes-count"]'),
                videos: document.querySelectorAll('[data-e2e="user-post-item"]').length,
                is_live: !!document.querySelector('[data-e2e="live-tab"]')
            };
        }
        """)

        await browser.close()

        DATA.update({
            "followers": parse_number(stats.get("followers")),
            "following": parse_number(stats.get("following")),
            "likes": parse_number(stats.get("likes")),
            "videos": stats.get("videos", 0),
            "is_live": stats.get("is_live", False),
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        print(f"[UPDATE] @{TARGET_USERNAME} | Followers: {DATA['followers']} | Live: {DATA['is_live']}")


def run_scraper():
    asyncio.run(fetch_user_data())


def scheduler_loop():
    schedule.every(30).seconds.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(1)


@app.route("/")
def index():
    return render_template("index.html", target_username=TARGET_USERNAME)


@app.route("/api/stats")
def api_stats():
    return jsonify(DATA)


if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    run_scraper()
    app.run(host="0.0.0.0", port=5000, debug=True)
