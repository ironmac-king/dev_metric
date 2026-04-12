"""获取完整的 HTML 输出"""
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

                # 检查所有 table 标签
                tables = page.locator('.result-panel table')
                print(f"表格总数: {tables.count()}")

                # 打印 table 的内容
                for i in range(tables.count()):
                    table_content = tables.nth(i).inner_html()
                    print(f"\n=== Table {i} ===")
                    print(table_content[:300])

                # 检查 h2 标签
                h2s = page.locator('.result-panel h2')
                print(f"\nh2 标签总数: {h2s.count()}")

                # 检查是否还有 ## 文本
                print(f"\n包含 ## 文本: {'##' in content}")
                print(f"包含 | 文本: {'|' in content}")

    browser.close()
