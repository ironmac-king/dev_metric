from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 打开智能问数页面
    page.goto('http://localhost:3001/#/ask')
    page.wait_for_load_state('networkidle')
    time.sleep(2)

    # 截图初始状态
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/test_01_initial.png', full_page=True)
    print("截图保存: test_01_initial.png")

    # 输入问题
    page.fill('input[type="text"], textarea', '最近15天销售额最高的sku，同比环比咋样')
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/test_02_input.png', full_page=True)
    print("截图保存: test_02_input.png")

    # 点击发送按钮
    page.click('button:has-text("发送"), button:has-text("问"), .send-btn, .submit-btn')
    page.wait_for_timeout(10000)  # 等待10秒处理

    # 截图结果
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/test_03_result.png', full_page=True)
    print("截图保存: test_03_result.png")

    # 获取页面内容
    content = page.content()
    print("页面内容长度:", len(content))

    # 打印控制台日志
    logs = page.evaluate("() => window.__CONSOLE_LOGS__ || []")
    if logs:
        print("控制台日志:", logs[-5:])  # 最近5条

    browser.close()
    print("测试完成")