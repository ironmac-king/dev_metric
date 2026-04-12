"""在浏览器中测试 formatResult 的各个步骤"""
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

            # 在浏览器中执行 formatResult 逻辑
            result = page.evaluate("""
                () => {
                    // 获取 rawMarkdown
                    const raw = window.rawMarkdown ? window.rawMarkdown.value :
                        document.querySelector('#app').__vue_app__.config.globalProperties.$store?.state?.analysis?.rawMarkdown || 'not found';

                    // 模拟 formatResult 的主要步骤
                    let text = '#  销售数据分析   ##  数据概览  |  指标 |  数值 |  参考标准  | |------|----------|';

                    // Step 1c: split headings
                    const before1c = text;
                    text = text.replace(/^(#{1,6}\\s+[^\\n]+?)\\s{2,}(#{1,6}\\s+)/gm, '$1\\n$2');

                    // Step 1e: split heading from table
                    const before1e = text;
                    text = text.replace(/^(#{1,6}\\s+[^\\n]+?)\\s+\\|/gm, '$1\\n|');

                    return {
                        before1c: before1c,
                        after1c: text,
                        before1e: before1e,
                        after1e: text
                    };
                }
            """)

            print("\n=== formatResult 调试 ===")
            print(f"1c 执行前: {result['before1c']}")
            print(f"1c 执行后: {result['after1c']}")
            print(f"1e 执行前: {result['before1e']}")
            print(f"1e 执行后: {result['after1e']}")

    browser.close()
