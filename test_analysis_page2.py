"""测试决策分析页面 - 详细版"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听控制台日志
    page.on("console", lambda msg: print(f"[Console] {msg.type}: {msg.text}"))

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    # 查找输入框并输入
    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告投放效果')
        print("已输入文本")

        # 点击发送按钮
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            print("已点击发送按钮")

            # 等待 loading 完成
            print("等待分析完成...")
            page.wait_for_selector('.result-text', timeout=60000)
            print("分析完成！")

            # 截图最终状态
            page.screenshot(path='C:/tmp/analysis_result2.png', full_page=True)
            print("截图已保存: /tmp/analysis_result2.png")

            # 获取 result-panel 内容
            result_text = page.locator('.result-text')
            if result_text.count() > 0:
                content = result_text.inner_html()
                print(f"\nresult-text 内容长度: {len(content)}")
                print(f"内容前800字符:\n{content[:800]}")

    browser.close()
    print("\n测试完成")
