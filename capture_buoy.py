import os, asyncio
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
    # timestamp in America/Chicago
    central = pytz.timezone("America/Chicago")
    now = datetime.now(central)
    ts = now.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUT_DIR, f"buoy_{ts}.pdf")

    print(f"[INFO] Capturing page at {now} → {out_file}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )

        # wide viewport to ensure all 4 columns render
        context = await browser.new_context(
            viewport={"width": 2400, "height": 1400},
            user_agent=SAFARI_UA,
            ignore_https_errors=True,
            locale="en-US",
            accept_downloads=True,
        )
        page = await context.new_page()

        print("[STEP] goto() …")
        await page.goto(URL, wait_until="domcontentloaded", timeout=180000)

        # allow iframes/widgets to finish
        print("[STEP] waiting for network idle …")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(6000)

        # scroll down to trigger any lazy content
        print("[STEP] scrolling …")
        try:
            scroll_height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            scroll_height = 2000
        y = 0
        while y < scroll_height:
            await page.evaluate(f"window.scrollTo(0, {y});")
            await page.wait_for_timeout(700)
            y += 400
        await page.evaluate("window.scrollTo(0,0);")
        await page.wait_for_timeout(1500)

        # Fit width on each PDF page; paginate vertically as needed
        content_width_px = await page.evaluate("document.documentElement.scrollWidth")
        target_width_px = 2400
        scale = min(1.0, target_width_px / max(content_width_px, 1))

        print(f"[STEP] Generating PDF … (scale={scale:.3f}, content_width={content_width_px}px)")
        await page.pdf(
            path=out_file,
            format="A2",
            landscape=True,
            print_background=True,
            margin={"top": "0.3in", "right": "0.3in", "bottom": "0.3in", "left": "0.3in"},
            prefer_css_page_size=False,
            scale=scale,
        )

        await browser.close()

    # verify file exists and is > 10 KB
    size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
    if size < 10_000:
        raise RuntimeError(f"PDF too small or missing: {out_file} (size={size} bytes)")
    print(f"[OK] Saved {out_file} ({size/1024:.1f} KB)")
    return out_file

async def main():
    await take_pdf_snapshot()

if __name__ == "__main__":
    asyncio.run(main())
