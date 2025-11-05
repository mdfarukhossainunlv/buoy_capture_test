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

MIN_BYTES = 10_000  # sanity threshold for non-empty files

def exists_ok(path: str, min_bytes: int = MIN_BYTES) -> bool:
    return os.path.exists(path) and os.path.getsize(path) >= min_bytes

async def take_capture():
    # timestamp in America/Chicago
    central = pytz.timezone("America/Chicago")
    now = datetime.now(central)
    ts = now.strftime("%Y%m%d_%H%M%S")

    png_path = os.path.join(OUT_DIR, f"buoy_{ts}.png")
    pdf_path = os.path.join(OUT_DIR, f"buoy_{ts}.pdf")

    print(f"[INFO] Starting capture at {now} (CT)")
    print(f"[INFO] URL: {URL}")
    print(f"[INFO] Output: PNG={png_path}, PDF={pdf_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )
        # Wider viewport so all 4 columns render without horizontal scroll
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

        # Allow iframes/widgets to finish loading
        print("[STEP] wait for networkidle + extra delay …")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(6000)

        # Gentle scroll to trigger any lazy-loaded content
        print("[STEP] scroll through page …")
        try:
            scroll_height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            scroll_height = 2000
        y = 0
        while y < scroll_height:
            await page.evaluate(f"window.scrollTo(0, {y});")
            await page.wait_for_timeout(600)
            y += 400
        await page.evaluate("window.scrollTo(0, 0);")
        await page.wait_for_timeout(1200)

        # --- Always take reliable PNG first ---
        print("[STEP] screenshot full_page PNG …")
        await page.screenshot(path=png_path, full_page=True, type="png")
        if exists_ok(png_path):
            print(f"[OK] PNG saved: {png_path} ({os.path.getsize(png_path)/1024:.1f} KB)")
        else:
            await browser.close()
            raise RuntimeError(f"PNG capture failed or too small: {png_path}")

        # --- Try Chromium PDF (fit width, paginate vertically) ---
        pdf_ok = False
        try:
            content_width_px = await page.evaluate("document.documentElement.scrollWidth")
            target_width_px = 2400
            scale = min(1.0, target_width_px / max(content_width_px, 1))
            print(f"[STEP] page.pdf() with A2 landscape (scale={scale:.3f}, content_width={content_width_px}px)")
            await page.pdf(
                path=pdf_path,
                format="A2",
                landscape=True,
                print_background=True,
                margin={"top": "0.3in", "right": "0.3in", "bottom": "0.3in", "left": "0.3in"},
                prefer_css_page_size=False,
                scale=scale,
            )
            pdf_ok = exists_ok(pdf_path)
            if pdf_ok:
                print(f"[OK] PDF via Chromium saved: {pdf_path} ({os.path.getsize(pdf_path)/1024:.1f} KB)")
            else:
                print("[WARN] Chromium PDF too small; will fallback to PNG→PDF")
        except Exception:
            print("[WARN] page.pdf() failed; will fallback to PNG→PDF")
            traceback.print_exc()

        await browser.close()

    # --- Fallback: convert PNG → PDF if needed ---
    if not pdf_ok:
        try:
            print("[STEP] Fallback: convert PNG → PDF")
            try:
                import img2pdf
                with open(png_path, "rb") as fin, open(pdf_path, "wb") as fout:
                    fout.write(img2pdf.convert(fin.read()))
                pdf_ok = exists_ok(pdf_path)
                if pdf_ok:
                    print(f"[OK] img2pdf created: {pdf_path} ({os.path.getsize(pdf_path)/1024:.1f} KB)")
                else:
                    print("[WARN] img2pdf output too small; will try Pillow")
            except Exception:
                from PIL import Image
                im = Image.open(png_path).convert("RGB")
                im.save(pdf_path, "PDF", resolution=300.0)
                pdf_ok = exists_ok(pdf_path)
                if pdf_ok:
                    print(f"[OK] Pillow created: {pdf_path} ({os.path.getsize(pdf_path)/1024:.1f} KB)")
                else:
                    print("[WARN] Pillow PDF output too small")
        except Exception:
            print("[ERROR] PNG→PDF fallback failed")
            traceback.print_exc()

    # Final checks
    if not exists_ok(png_path):
        raise RuntimeError("Final check failed: PNG missing or too small.")
    if not exists_ok(pdf_path):
        raise RuntimeError("Final check failed: PDF missing or too small.")

    print(f"[DONE] PNG: {png_path}")
    print(f"[DONE] PDF: {pdf_path}")
    return png_path, pdf_path

async def main():
    await take_capture()

if __name__ == "__main__":
    asyncio.run(main())
