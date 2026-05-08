"""测试决策分析页面 - 捕获错误和响应状态"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听 console 所有消息
    def on_console(msg):
        print(f"[CONSOLE {msg.type}] {msg.text[:200]}")
    page.on("console", on_console)

    # 监听 page 错误
    def on_page_error(err):
        print(f"[PAGE ERROR] {err}")
    page.on("pageerror", on_page_error)

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')
    print("页面加载完成")

    # 查找输入框并输入
    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        print("已输入文本")

        # 点击发送按钮
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            print("已点击发送按钮，等待分析完成...")

            # 等待 SSE 流式传输完成
            page.wait_for_timeout(30000)

            # 检查 result-panel 内容
            result_panel = page.locator('.result-panel .result-text')
            if result_panel.count() > 0:
                content = result_panel.inner_html()
                print(f"\n=== result-text HTML ({len(content)} 字符) ===")
                with open('C:/tmp/result_html.txt', 'w', encoding='utf-8') as f:
                    f.write(content)
                print("HTML 已保存到 C:/tmp/result_html.txt")

                # 检查表格
                tables = page.locator('.result-panel table')
                print(f"\n=== 表格检查 ===")
                print(f"表格数量: {tables.count()}")
            else:
                print("\n未找到 .result-text 元素")

            # 检查 loading 状态
            loading = page.locator('.result-loading')
            if loading.count() > 0 and loading.first.is_visible():
                print("\n仍在 loading 状态...")

    browser.close()
    print("\n测试完成")