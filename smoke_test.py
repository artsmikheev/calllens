from pathlib import Path
import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"http://127.0.0.1:{os.getenv('TEST_PORT', '8101')}")
    page.wait_for_load_state('networkidle')
    assert page.locator('text=Соберите входные данные').is_visible()
    assert page.locator('#manualList .criterion-row').count() == 6
    page.set_input_files('#audioFile', {'name': 'bad.pdf', 'mimeType': 'application/pdf', 'buffer': b'not audio'})
    assert 'Формат не поддерживается' in page.locator('#formStatus').inner_text()
    page.set_input_files('#audioFile', {'name': 'sample.mp4', 'mimeType': 'video/mp4', 'buffer': b'fake video'})
    assert 'sample.mp4' in page.locator('#audioMeta').inner_text()
    page.click('#addCriterion')
    assert page.locator('#manualList .criterion-row').count() == 7
    page.screenshot(path='/tmp/calllens-smoke.png', full_page=True)
    print('Smoke test passed; screenshot=/tmp/calllens-smoke.png')
    browser.close()
