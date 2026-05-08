"""检查 SSE chunk 数据"""
from playwright.sync_api import sync_playwright
import sys

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听 SSE 消息
    def on_console(msg):
        text = msg.text
        # 只显示包含特定关键词的消息
        if 'chunk' in text.lower() and len(text) > 50:
            # 显示 chunk 数据的关键部分
            print(f"SSE chunk: {text[:150]}")

    page.on("console", on_console)

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

    browser.close()
