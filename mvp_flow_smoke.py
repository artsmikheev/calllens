import os
from playwright.sync_api import sync_playwright

port = os.getenv('TEST_PORT', '8125')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    page.goto(f'http://127.0.0.1:{port}/')
    page.wait_for_load_state('networkidle')
    page.wait_for_function("document.querySelector('#aiStatus')?.textContent === 'Demo-режим'")
    assert page.locator('#aiStatus').inner_text() == 'Demo-режим'
    page.set_input_files('#audioFile', {'name': 'demo-call.mp4', 'mimeType': 'video/mp4', 'buffer': b'demo fixture'})
    assert 'demo-call.mp4' in page.locator('#audioMeta').inner_text()
    page.click('#analyzeButton')
    page.wait_for_selector('#resultsSection:not(.hidden)', timeout=15000)
    assert page.locator('text=Разбор готов').is_visible()
    assert page.locator('text=Демонстрационная цитата').count() >= 1
    assert page.locator('#scoreCard').is_visible()
    page.screenshot(path='/tmp/calllens-mvp-stage3-flow.png', full_page=True)
    print('MVP flow smoke passed; screenshot=/tmp/calllens-mvp-stage3-flow.png')
    browser.close()
