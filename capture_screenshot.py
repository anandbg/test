#!/usr/bin/env python3
"""Capture screenshot of the HTML page"""
import asyncio
from playwright.async_api import async_playwright
import os

async def capture_screenshot():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Set viewport size for a good screenshot
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Load the HTML file
        html_path = os.path.abspath('/workspace/index.html')
        file_url = f'file://{html_path}'
        
        print(f"Loading: {file_url}")
        await page.goto(file_url, wait_until='networkidle')
        
        # Wait a bit for images to load
        await page.wait_for_timeout(3000)
        
        # Take screenshot
        screenshot_path = '/workspace/page_screenshot.png'
        await page.screenshot(path=screenshot_path, full_page=True)
        
        print(f"Screenshot saved to: {screenshot_path}")
        
        await browser.close()
        return screenshot_path

if __name__ == '__main__':
    screenshot_path = asyncio.run(capture_screenshot())
    print(f"\n✅ Screenshot captured: {screenshot_path}")
