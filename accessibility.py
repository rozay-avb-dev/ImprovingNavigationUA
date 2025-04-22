import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

async def capture_building_screenshot(building_name, output_format="png"):
    # Setup save directory
    save_dir = r"C:\Users\ual-laptop\Desktop\Capstone\ImprovingNavigationUA\Captures"
    os.makedirs(save_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Headless = faster
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print("Navigating to UofA map...")
        await page.goto("https://map.arizona.edu/", wait_until="domcontentloaded")
        
        print(f"Searching for: {building_name}")
        search_box = page.locator("input.esri-search__input")
        await search_box.click()
        await search_box.fill(building_name)

        # Try interacting with the dropdown
        suggestion_selector = "li.esri-search__suggestion-item, .esri-search__suggestions-menu li"
        try:
            await page.wait_for_selector(suggestion_selector, timeout=4000)
            first_suggestion = page.locator(suggestion_selector).first
            if await first_suggestion.is_visible():
                await page.evaluate("(el) => el.click()", await first_suggestion.element_handle())
                print("Clicked first suggestion.")
            else:
                print("Suggestion not visible — pressing Enter instead.")
                await search_box.press("Enter")
        except Exception as e:
            print(f"Dropdown not available, fallback to Enter. Error: {e}")
            await search_box.press("Enter")

        # Wait for the popup info card to appear
        try:
            await page.wait_for_selector("div.esri-popup__main-container", timeout=5000)
            print("Popup appeared.")
        except:
            print("Popup did not appear — capturing whatever is visible.")

        # Save screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = ''.join(c if c.isalnum() else '_' for c in building_name)
        filename = f"map_{safe_name}_{timestamp}.{output_format}"
        save_path = os.path.join(save_dir, filename)

        await page.screenshot(path=save_path)
        print(f"Screenshot saved to: {save_path}")

        await browser.close()

if __name__ == "__main__":
    building = input("Enter building name (e.g., Old Main): ")
    output_format = "png"
    asyncio.run(capture_building_screenshot(building, output_format))
