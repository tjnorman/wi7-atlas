"""Render README and site media from the real site code and the current data.

Outputs
  docs/media/hero.webp        animated README hero (district outline drawing in)
  docs/media/tour.webp        short, sped-up README tour
  site/media/tour.mp4|webm    the full tour video, linked from the README and the site
  site/media/poster.jpg       first frame of the tour
  site/media/social.png       1200 x 630 social card
  docs/media/screens/*.png    light and dark screenshots of each section

Usage: python tools/render_media.py [--data data/wi-07] [--out-docs docs/media] [--out-site site/media]
Requires Playwright (Chromium) and ffmpeg.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import pathlib
import shutil
import subprocess
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent


def serve(directory: pathlib.Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


async def record(url: str, out_dir: pathlib.Path, size: tuple[int, int], until_js: str | None, seconds: float,
                 scheme: str = "light", chrome: str | None = None) -> pathlib.Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome) if chrome else await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": size[0], "height": size[1]}, color_scheme=scheme,
                                        record_video_dir=str(out_dir), record_video_size={"width": size[0], "height": size[1]})
        page = await ctx.new_page()
        await page.goto(url)
        if until_js:
            for _ in range(int(seconds * 2)):
                if await page.evaluate(until_js):
                    break
                await page.wait_for_timeout(500)
            await page.wait_for_timeout(1200)
        else:
            await page.wait_for_timeout(int(seconds * 1000))
        video = page.video
        await ctx.close()
        path = pathlib.Path(await video.path())
        await browser.close()
        return path


async def screenshots(base: str, out: pathlib.Path, chrome: str | None) -> None:
    from playwright.async_api import async_playwright

    out.mkdir(parents=True, exist_ok=True)
    sections = ["top", "glance", "land", "people", "work", "dollars", "seat", "counties", "trust"]
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome) if chrome else await p.chromium.launch()
        for scheme in ("light", "dark"):
            page = await browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme=scheme, device_scale_factor=2)
            await page.goto(base)
            await page.wait_for_timeout(5500)
            for s in sections:
                await page.evaluate(f"document.getElementById('{s}').scrollIntoView({{block: 'start'}})")
                await page.wait_for_timeout(1600)
                await page.screenshot(path=str(out / f"{s}-{scheme}.png"))
            await page.close()
        page = await browser.new_page(viewport={"width": 1200, "height": 630}, color_scheme="light")
        await page.goto(base)
        await page.wait_for_timeout(5500)
        await page.screenshot(path=str(out.parent / "social.png"))
        await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "wi-07"))
    ap.add_argument("--out-docs", default=str(ROOT / "docs" / "media"))
    ap.add_argument("--out-site", default=str(ROOT / "site" / "media"))
    ap.add_argument("--chrome", default=None, help="path to a Chrome binary (optional)")
    args = ap.parse_args()
    docs, site_media = pathlib.Path(args.out_docs), pathlib.Path(args.out_site)
    docs.mkdir(parents=True, exist_ok=True)
    site_media.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        web = tmp / "web"
        shutil.copytree(ROOT / "site", web, ignore=shutil.ignore_patterns("media"))
        shutil.copytree(args.data, web / "data")
        httpd, port = serve(web)
        base = f"http://127.0.0.1:{port}/"
        try:
            # 1. Hero: the outline draws itself and the counties light up.
            hero = asyncio.run(record(base, tmp / "hero", (1600, 900), None, 7.5, chrome=args.chrome))
            ffmpeg("-ss", "0.6", "-i", str(hero), "-t", "6.4", "-vf", "fps=18,scale=1200:-1:flags=lanczos",
                   "-loop", "0", "-quality", "72", "-compression_level", "6", str(docs / "hero.webp"))
            # 2. Tour: the scripted film mode, recorded end to end.
            tour = asyncio.run(record(base + "?film=1", tmp / "tour", (1600, 900), "window.__filmDone === true", 150,
                                      chrome=args.chrome))
            ffmpeg("-i", str(tour), "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", "-an", str(site_media / "tour.mp4"))
            ffmpeg("-i", str(tour), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "46", "-row-mt", "1", "-deadline", "realtime",
                   "-cpu-used", "8", "-an", str(site_media / "tour.webm"))
            ffmpeg("-ss", "5", "-i", str(tour), "-frames:v", "1", "-q:v", "3", str(site_media / "poster.jpg"))
            ffmpeg("-i", str(tour), "-vf", "setpts=PTS/2.2,fps=8,scale=960:-1:flags=lanczos", "-loop", "0",
                   "-quality", "60", "-compression_level", "6", str(docs / "tour.webp"))
            # 3. Screenshots and the social card.
            asyncio.run(screenshots(base, docs / "screens", args.chrome))
            if (docs / "social.png").exists():
                shutil.move(str(docs / "social.png"), site_media / "social.png")
        finally:
            httpd.shutdown()
    for f in sorted([*docs.glob("*.webp"), *site_media.glob("*")]):
        print(f"  {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}  {f.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
