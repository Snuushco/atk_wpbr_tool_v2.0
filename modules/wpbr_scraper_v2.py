import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # zichtbaar voor debug
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        print("⏳ Bezoek de WPBR-pagina...")
        await page.goto("https://www.justis.nl/registers/wpbr-register", wait_until='networkidle')
        await page.wait_for_timeout(2000)

        # Stap 1: Klik op de JSON-tab
        try:
            await page.get_by_text("JSON", exact=False).click()
            print("✅ JSON-tab geselecteerd.")
        except Exception as e:
            print("❌ Kon JSON-tab niet klikken:", e)

        await page.wait_for_timeout(1500)

        # Stap 2: Download via async context
        try:
            async with page.expect_download() as download_info:
                await page.click("text=Download")
            download = await download_info.value
            path = await download.path()
            print(f"✅ Bestand automatisch gedownload naar tijdelijk pad: {path}")
            await download.save_as("wpbr-register.json")
            print("📁 Bestand opgeslagen als: wpbr-register.json")
        except Exception as e:
            print("❌ Fout bij downloaden:", e)

        await browser.close()

asyncio.run(run())
