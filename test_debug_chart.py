"""调试图表数据"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听控制台消息
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
    page.wait_for_timeout(2000)

    # 在页面上执行 JavaScript 获取 rawMarkdown
    raw_markdown = page.evaluate("() => window.__rawMarkdown || 'NOT FOUND'")
    print(f"\nrawMarkdown 内容长度: {len(raw_markdown) if raw_markdown != 'NOT FOUND' else 0}")

    if raw_markdown and raw_markdown != 'NOT FOUND':
        if '{CHART_DATA:' in raw_markdown:
            print("✓ 包含 {CHART_DATA:")
            idx = raw_markdown.find('{CHART_DATA:')
            print(f"图表数据位置: {idx}")
            print(f"图表数据预览: {raw_markdown[idx:idx+200]}...")
        else:
            print("✗ 不包含 {CHART_DATA:")

    page.screenshot(path='C:/tmp/chart_debug.png', full_page=True)
    print("\n截图已保存")
