"""测试 SSE 流是否完整"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听所有 console 消息
    page.on("console", lambda msg: print(f"[{msg.type}] {msg.text[:100]}") if 'formatResult' in msg.text or 'done' in msg.text.lower() or 'SSE' in msg.text else None)

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    # 查找输入框并输入
    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        print("已输入文本")

        # 点击发送按钮
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            print("已点击发送按钮")

            # 等待更长时间让 SSE 完成
            page.wait_for_timeout(35000)

            # 检查 result-panel 内容
            result_panel = page.locator('.result-panel .result-text')
            if result_panel.count() > 0:
                content = result_panel.inner_html()
                print(f"\nresult-text 长度: {len(content)}")
                # 检查是否有表格
                tables = page.locator('.result-panel table')
                print(f"表格数量: {tables.count()}")
                # 检查是否有 h2 标签
                h2s = page.locator('.result-panel h2')
                print(f"h2 标签数量: {h2s.count()}")
                # 检查原始文本
                if '##' in content:
                    print("警告: HTML 中仍包含 ## 文本（应该被转换为 h2）")
                if '{CHART_DATA' in content:
                    print("警告: HTML 中仍包含 {CHART_DATA}（应该被移除）")

    browser.close()