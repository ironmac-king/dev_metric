"""测试 formatResult 调用前的 cleanedMarkdown 内容"""
from playwright.sync_api import sync_playwright
import sys

# 设置 stdout 为 UTF-8
sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 监听 console 消息
    def on_console(msg):
        try:
            text = msg.text
            if 'cleanedMarkdown' in text or 'rawMarkdown' in text or 'formatResult' in text:
                print(f"[{msg.type}] {text[:500]}")
        except:
            pass

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

            # 等待更长时间
            page.wait_for_timeout(60000)

            # 检查结果
            result = page.locator('.result-panel .result-text')
            if result.count() > 0:
                content = result.inner_html()
                print(f"\n结果长度: {len(content)}")
                print(f"包含 ## 文本: {'##' in content}")
                print(f"包含 h2 标签: {'<h2>' in content}")
                print(f"包含 h1 标签: {'<h1>' in content}")
            else:
                print("没有找到 result-panel")

    browser.close()
