"""直接在浏览器中测试 regex"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    # 直接在页面中执行 JavaScript 测试 regex
    result = page.evaluate("""
        () => {
            const text = '#  销售数据分析   ##  数据概览  |  指标 |  数值 |';

            // 模拟 formatResult 中的 heading split
            const result = text.replace(/^(#{1,6}\\s+[^\\n]+?)\\s{2,}(#{1,6}\\s+)/gm, '$1\\n$2');

            return {
                input: text,
                output: result,
                hasNewline: result.includes('\\n')
            };
        }
    """)

    print(f"输入: {result['input']}")
    print(f"输出: {result['output']}")
    print(f"包含换行: {result['hasNewline']}")

    browser.close()
