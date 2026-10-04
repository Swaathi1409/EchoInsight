import asyncio
from playwright.async_api import async_playwright
import os

PAGES = [
    "/",
    "/conversations",
    "/commitments",
    "/quality",
    "/checklists",
    "/cases",
    "/action/recovery",
    "/action/recurring",
    "/action/initiatives",
    "/action/agents",
    "/admin"
]

async def run():
    os.makedirs(".backup/screenshots/light/1440", exist_ok=True)
    os.makedirs(".backup/screenshots/light/820", exist_ok=True)
    os.makedirs(".backup/screenshots/dark/1440", exist_ok=True)
    os.makedirs(".backup/screenshots/dark/820", exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        # Login
        await page.goto("http://localhost:3000/#/login")
        await page.fill("#login-username", "admin")
        await page.fill("#login-password", "changeme_admin")
        
        await page.click("button[type=submit]")
        await page.wait_for_timeout(2000) # wait for login to finish
        
        base_url = "http://localhost:3000/#"

        for theme in ["light", "dark"]:
            # Set theme
            if theme == "dark":
                await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
            else:
                await page.evaluate("document.documentElement.setAttribute('data-theme', 'light')")
                
            for size in [(1440, 900), (820, 1024)]:
                width, height = size
                await page.set_viewport_size({"width": width, "height": height})
                
                for route in PAGES:
                    await page.goto(f"{base_url}{route}")
                    await page.wait_for_timeout(2000) # Let it load
                    name = route.strip('/').replace('/', '_') or 'overview'
                    await page.screenshot(path=f".backup/screenshots/{theme}/{width}/{name}.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
