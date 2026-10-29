import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"http://127.0.0.1:{os.getenv('TEST_PORT', '8103')}/dashboard.html")
    page.wait_for_load_state('networkidle')
    assert page.locator('text=Эффективность менеджеров').is_visible()
    assert page.locator('#kpiCalls').inner_text() == '12'
    assert page.locator('#managerBars .manager-row').count() == 4
    assert page.locator('#callsTable tr').count() == 12
    page.select_option('#styleFilter', 'Результатный стратег')
    assert page.locator('#kpiCalls').inner_text() == '3'
    assert page.locator('#styleMatrix .matrix-cell').count() >= 5
    page.screenshot(path='/tmp/calllens-dashboard.png', full_page=True)
    print('Dashboard smoke test passed; screenshot=/tmp/calllens-dashboard.png')
    browser.close()
