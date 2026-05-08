"""检查实际的 rawMarkdown 内容"""
from playwright.sync_api import sync_playwright
import sys

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    # 输入并发送
    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            print("等待 SSE 完成...")
            page.wait_for_timeout(60000)

            # 获取实际的 result-panel 内容
            result = page.locator('.result-panel .result-text')
            if result.count() > 0:
                content = result.inner_html()
                print(f"\n=== result-panel HTML (前500字符) ===")
                print(content[:500])

            # 检查是否有 table 标签
            tables = page.locator('.result-panel table')
            print(f"\n表格数量: {tables.count()}")

            # 检查 h2 标签
            h2s = page.locator('.result-panel h2')
            print(f"h2 数量: {h2s.count()}")

            if h2s.count() > 0:
                for i in range(min(3, h2s.count())):
                    print(f"h2[{i}]: {h2s.nth(i).inner_html()[:100]}")

    browser.close()
