"""直接测试 formatResult 函数"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 打开页面
    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    # 在页面中直接测试 formatResult
    test_markdown = """# 销售数据分析
## 数据概览
| 指标 | 数值 | 参考标准 |
| ------|------|---------- |
| 销售额 | ¥754807145.12 | 优秀 |
"""

    # 调用 formatResult 并获取结果
    result = page.evaluate("""
        () => {
            // 找到 Vue 实例中的 formatResult 函数
            const vueApp = document.querySelector('#app').__vue_app__;
            if (vueApp) {
                // 尝试调用 formatResult
                const formatResult = window.formatResult;
                if (formatResult) {
                    return formatResult(arguments[0]);
                }
                return 'formatResult not found on window';
            }
            return 'Vue app not found';
        }
    """, test_markdown)

    print(f"测试结果: {result[:500] if result else 'null'}")

    # 检查表格
    tables = page.locator('.result-table')
    print(f"表格数量: {tables.count()}")

    browser.close()