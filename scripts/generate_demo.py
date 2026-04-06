"""
Generate an animated GIF demo of the ARIA dashboard.

What this does:
  1. Starts the FastAPI server (uvicorn) in a subprocess.
  2. Uses Playwright to visit each of the five dashboard pages.
  3. Takes a full-page screenshot of each page after charts have loaded.
  4. Stitches the screenshots into an animated GIF with Pillow.
  5. Saves the result to docs/demo.gif.

Requirements:
  pip install playwright pillow
  playwright install chromium

Run from the project root:
  python scripts/generate_demo.py
"""

import os
import subprocess
import sys
import time
import signal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8099"   # use a non-standard port to avoid conflicts
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "demo.gif")
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "_screenshots")

PAGES = [
    ("/",             "01_overview",      4000),   # (path, name, ms to wait for charts)
    ("/causal",       "02_causal",        5000),   # causal model takes longer
    ("/explainer",    "03_explainer",     4000),
    ("/alerts",       "04_alerts",        3000),
    ("/architecture", "05_architecture",  3000),
]

# Each frame is shown for this many milliseconds in the output GIF.
# Two frames per page: one on arrival, one after a short pause.
FRAME_DURATION_MS = 1200

# Viewport — 1280x800 fits the sidebar + main content comfortably.
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def wait_for_server(url: str, timeout: int = 30) -> bool:
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


def start_server() -> subprocess.Popen:
    """Start uvicorn in a subprocess. Returns the process handle."""
    venv_uvicorn = os.path.join(
        os.path.dirname(__file__), "..", ".venv", "bin", "uvicorn"
    )
    uvicorn_bin = venv_uvicorn if os.path.exists(venv_uvicorn) else "uvicorn"

    proc = subprocess.Popen(
        [
            uvicorn_bin,
            "src.api.main:app",
            "--host", "127.0.0.1",
            "--port", "8099",
            "--log-level", "error",
        ],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def take_screenshots(screenshot_dir: str) -> list[str]:
    """Use Playwright to visit each page and take screenshots. Returns file paths."""
    from playwright.sync_api import sync_playwright

    os.makedirs(screenshot_dir, exist_ok=True)
    paths = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            color_scheme="dark",
        )
        page = context.new_page()

        for path, name, wait_ms in PAGES:
            url = BASE_URL + path
            page.goto(url, wait_until="networkidle")

            # Wait for the page's own JS to finish rendering charts.
            page.wait_for_timeout(wait_ms)

            # Screenshot at natural scroll position (top of page).
            out = os.path.join(screenshot_dir, f"{name}.png")
            page.screenshot(path=out, full_page=False)
            paths.append(out)

            # For pages with interactive elements, capture a second frame
            # scrolled slightly to show content below the fold.
            if path in ("/", "/causal", "/explainer"):
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(600)
                out2 = os.path.join(screenshot_dir, f"{name}_scroll.png")
                page.screenshot(path=out2, full_page=False)
                paths.append(out2)

        browser.close()

    return paths


def build_gif(screenshot_paths: list[str], output_path: str) -> None:
    """Combine screenshots into an animated GIF using Pillow."""
    from PIL import Image

    frames = []
    for p in screenshot_paths:
        img = Image.open(p).convert("RGB")
        # Resize to a reasonable GIF size — full 1280px makes very large files.
        img = img.resize((960, 600), Image.LANCZOS)
        frames.append(img)

    if not frames:
        print("No screenshots captured — GIF not created.")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
    )
    size_kb = os.path.getsize(output_path) // 1024
    print(f"GIF saved: {output_path}  ({size_kb} KB, {len(frames)} frames)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright as _  # noqa: F401
    except ImportError:
        print("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    try:
        from PIL import Image as _  # noqa: F401
    except ImportError:
        print("Pillow is not installed. Run: pip install pillow")
        sys.exit(1)

    print("Starting ARIA server on port 8099...")
    server = start_server()

    try:
        if not wait_for_server(BASE_URL, timeout=30):
            print("Server did not start within 30 seconds. Check that dependencies are installed.")
            server.terminate()
            sys.exit(1)

        print("Server ready. Taking screenshots...")
        paths = take_screenshots(SCREENSHOT_DIR)
        print(f"Captured {len(paths)} frames.")

        print("Building GIF...")
        build_gif(paths, os.path.abspath(OUTPUT_PATH))

    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=5)
        print("Server stopped.")


if __name__ == "__main__":
    main()
