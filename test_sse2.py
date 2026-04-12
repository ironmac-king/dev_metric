"""测试 SSE done 事件"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听所有 console
    def on_console(msg):
        text = msg.text
        if any(x in text for x in ['done', 'SSE', 'formatResult', '渲染', '完成']):
            try:
                print(f"[{msg.type}] {text[:150]}")
            except:
                pass

    page.on("console", on_console)

    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            print("等待 SSE 完成...")

            # 等待更长时间
            page.wait_for_timeout(60000)  # 60秒

            # 检查结果
            result = page.locator('.result-panel .result-text')
            if result.count() > 0:
                content = result.inner_html()
                print(f"\n结果长度: {len(content)}")
                print(f"包含 ## 文本: {'##' in content}")
                print(f"包含 h2 标签: {'<h2>' in content}")
                print(f"包含 CHART_DATA: {'CHART_DATA' in content}")
            else:
                print("没有找到 result-panel")

    browser.close()