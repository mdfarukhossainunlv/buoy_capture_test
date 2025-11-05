import os, asyncio, traceback
from datetime import datetime
from playwright.async_api import async_playwright
import pytz

URL = "https://www.southeastern.edu/college-of-science-and-technology/center-for-environmental-research/lakemaurepas/buoydata/"
OUT_DIR = "captures"
os.makedirs(OUT_DIR, exist_ok=True)

SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Safari/605.1.15"
)

async def take_pdf_snapshot():
    central = pytz.timezone("America/Chicago")
    now = datetime.now(central)
    ts = now.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUT_DIR, f"buoy_{ts}.pdf")

    print(f"[INFO] Capturing page at {now}")
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

        print("[STEP] Loading page…")
        await page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        await page.wait_for_timeout(8000)

        print("[STEP] Scrolling to render all elements…")
        scroll_height = await page.evaluate("document.body.scrollHeight")
        y = 0
        while y < scroll_height:
            await page.evaluate(f"window.scrollTo(0, {y});")
            await page.wait_for_timeout(1000)
            y += 300
        await page.evaluate("window.scrollTo(0, 0);")
        await page.wait_for_timeout(2000)

        print("[STEP] Generating PDF…")
        await page.pdf(
            path=out_file,
            format="A2",
            landscape=True,
            print_background=True,
            margin={"top": "0.3in", "bottom": "0.3in", "left": "0.3in", "right": "0.3in"},
        )

        await browser.close()

    print(f"[OK] Saved {out_file}")
    return out_file

async def main():
    await take_pdf_snapshot()

if __name__ == "__main__":
    asyncio.run(main())
