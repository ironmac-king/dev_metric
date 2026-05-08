"""测试图表渲染"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.on("console", lambda msg: print(f"[Console] {msg.type}: {msg.text}"))

    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    textarea = page.locator('textarea')
    textarea.fill('分析近30天广告投放效果')

    send_btn = page.locator('.send-btn')
    send_btn.click()

    print("等待分析完成...")
    page.wait_for_selector('.result-text', timeout=90000)
    page.wait_for_timeout(2000)

    page.screenshot(path='C:/tmp/chart_test.png', full_page=True)

    # 检查图表
    charts = page.locator('.chart-container')
    print(f"图表容器数量: {charts.count()}")

    for i in range(charts.count()):
        chart = charts.nth(i)
        box = chart.bounding_box()
        print(f"图表 {i}: bounding_box={box}")

    print("\n测试完成")
