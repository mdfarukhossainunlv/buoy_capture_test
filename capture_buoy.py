import os, asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import pytz

# 🌎 Time zone for Baton Rouge
ZONE = pytz.timezone("America/Chicago")

URL = "https://www.southeastern.edu/college-of-science-and-technology/center-for-environmental-research/lakemaurepas/buoydata/"
OUT_DIR = "captures"
os.makedirs(OUT_DIR, exist_ok=True)

SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Safari/605.1.15"
)

async def take_pdf_snapshot():
    now_local = datetime.now(ZONE)
    ts_local = now_local.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUT_DIR, f"buoy_{ts_local}_BatonRouge.pdf")

    print("========================================")
    print(f"[INFO] Baton Rouge local time: {now_local.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print(f"[INFO] Saving file: {out_file}")
    print("========================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )

        context = await browser.new_context(
            viewport={"width": 2400, "height": 1400},
            user_agent=SAFARI_UA,
            ignore_https_errors=True,
            locale="en-US",
            accept_downloads=True,
        )

        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        await page.wait_for_timeout(8000)

        # Scroll down to trigger all chart loading
        scroll_height = await page.evaluate("document.body.scrollHeight")
        y = 0
        while y < scroll_height:
            await page.evaluate(f"window.scrollTo(0, {y});")
            await page.wait_for_timeout(800)
            y += 400

        await page.evaluate("window.scrollTo(0, 0);")
        await page.wait_for_timeout(2000)

        # Save as PDF (A2 landscape)
        await page.pdf(
            path=out_file,
            format="A2",
            landscape=True,
            print_background=True,
            margin={"top": "0.3in", "bottom": "0.3in", "left": "0.3in", "right": "0.3in"},
        )

        await browser.close()

    print(f"[OK] PDF saved successfully → {out_file}")
    return out_file

async def main():
    await take_pdf_snapshot()

if __name__ == "__main__":
    asyncio.run(main())
