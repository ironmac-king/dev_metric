"""检查 HTML 输出结构"""
from playwright.sync_api import sync_playwright
import sys

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            page.wait_for_timeout(60000)

            result = page.locator('.result-panel .result-text')
            if result.count() > 0:
                content = result.inner_html()

                # 打印完整 HTML
                print("=== result-panel HTML 完整内容 ===")
                print(content)
                print("\n=== 统计 ===")
                print(f"表格数量: {content.count('<table')}")
                print(f"h2 数量: {content.count('<h2>')}")
                print(f"h3 数量: {content.count('<h3>')}")
                print(f"段落数量: {content.count('<p>')}")

    browser.close()
