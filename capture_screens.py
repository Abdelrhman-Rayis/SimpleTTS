"""Capture screenshots of Munfath for the pitch deck."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT_DIR = Path("/Users/rayis/SimpleTTS/deck_assets")
OUT_DIR.mkdir(exist_ok=True)
URL = "http://127.0.0.1:8002"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Desktop light
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate("""() => {
            document.documentElement.setAttribute('data-theme','light');
            try { localStorage.removeItem('simpletts-theme'); } catch(_) {}
        }""")
        await page.wait_for_timeout(900)
        await page.screenshot(path=str(OUT_DIR / "home_light.png"), full_page=False)
        print("home_light.png saved")

        # Desktop dark
        await page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(OUT_DIR / "home_dark.png"), full_page=False)
        print("home_dark.png saved")
        await ctx.close()

        # Player close-up (clip the bottom bar)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        await page.wait_for_timeout(600)
        bar = page.locator(".sidebar")
        await bar.screenshot(path=str(OUT_DIR / "player_light.png"))
        print("player_light.png saved")

        await page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        await page.wait_for_timeout(500)
        await bar.screenshot(path=str(OUT_DIR / "player_dark.png"))
        print("player_dark.png saved")
        await ctx.close()

        # Mobile (375x812)
        ctx = await browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=3, is_mobile=True)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(OUT_DIR / "mobile_light.png"), full_page=False)
        print("mobile_light.png saved")

        await page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT_DIR / "mobile_dark.png"), full_page=False)
        print("mobile_dark.png saved")
        await ctx.close()

        # Hero crop (top portion of desktop light)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        await page.wait_for_timeout(700)
        hero = page.locator(".home-hero")
        await hero.screenshot(path=str(OUT_DIR / "hero_light.png"))
        print("hero_light.png saved")
        await ctx.close()

        await browser.close()

asyncio.run(main())
