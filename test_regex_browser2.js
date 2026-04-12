"""直接在浏览器中测试实际的文本处理"""
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

            # 直接测试实际的文本处理
            result = page.evaluate("""
                () => {
                    // 模拟实际数据
                    const text = '#  销售数据分析   ##  数据概览  |  指标 |  数值 |  参考标准  | |------|----------|';

                    // 1. trim
                    let processed = text.trim();

                    // 2. 1c: split headings
                    processed = processed.replace(/^(#{1,6}\\s+[^\\n]+?)\\s{2,}(#{1,6}\\s+)/gm, '$1\\n$2');

                    // 3. 1e: split heading from table
                    processed = processed.replace(/^(#{1,6}\\s+[^\\n]+?)\\s+\\|/gm, '$1\\n|');

                    // 4. normalize line endings
                    processed = processed.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');

                    return {
                        after1c_and_1e: processed,
                        lines: processed.split('\\n').slice(0, 5)
                    };
                }
            """)

            print("\n=== 浏览器中测试 regex ===")
            print(f"处理后文本:\n{result['after1c_and_1e'][:200]}")
            print(f"\n前5行:")
            for i, line in enumerate(result['lines']):
                print(f"  {i}: {line[:50]}")

    browser.close()
