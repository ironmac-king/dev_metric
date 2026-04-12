"""在浏览器中测试 table detection"""
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

            # 测试 table detection
            result = page.evaluate("""
                () => {
                    const testText = '#  销售数据分析\\n##  数据概览\\n|  指标 |  数值 |  参考标准  |\\n| ------|------|---------- |\\n| 销售额 | 100 |';

                    // 模拟 formatResult 的 table detection
                    const lines = testText.split('\\n');
                    const tableLines = [];

                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];
                        const trimmed = line.trim();

                        // Check if it's a table row
                        const isTableRow = trimmed.startsWith('|') && trimmed.endsWith('|');

                        // Check if it's a separator
                        const separatorPattern = /^[\\|\\s\\-:]+$/;
                        const hasDashSequence = /[\\-:\\s]{3,}/.test(trimmed) || trimmed.includes('---');
                        const isTableSeparator = separatorPattern.test(trimmed) && hasDashSequence;

                        tableLines.push({
                            line: line.substring(0, 50),
                            trimmed: trimmed.substring(0, 50),
                            isTableRow,
                            isTableSeparator
                        });
                    }

                    return tableLines;
                }
            """)

            print("\n=== Table Detection 测试 ===")
            for i, item in enumerate(result):
                print(f"Line {i}: '{item['line']}'")
                print(f"  trimmed: '{item['trimmed']}'")
                print(f"  isTableRow: {item['isTableRow']}, isTableSeparator: {item['isTableSeparator']}")

    browser.close()
