"""调试图表数据 - v2"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def handle_console(msg):
        print(f"[Console] {msg.type}: {msg.text}")

    page.on("console", handle_console)

    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    textarea = page.locator('textarea')
    textarea.fill('分析近30天广告投放效果')

    send_btn = page.locator('.send-btn')
    send_btn.click()

    print("等待分析完成...")
    page.wait_for_selector('.result-text', timeout=90000)
    page.wait_for_timeout(3000)

    # 获取 result-text 内容
    result_text = page.locator('.result-text')
    if result_text.count() > 0:
        content = result_text.inner_html()
        print(f"\nresult-text 内容长度: {len(content)}")

        if '{CHART_DATA:' in content:
            print("result-text HTML 中包含 {CHART_DATA:")
            idx = content.find('{CHART_DATA:')
            print(f"图表数据预览: {content[idx:idx+300]}...")
        else:
            print("result-text HTML 中不包含 {CHART_DATA:")

    page.screenshot(path='C:/tmp/chart_debug2.png', full_page=True)
    print("\n截图已保存")
