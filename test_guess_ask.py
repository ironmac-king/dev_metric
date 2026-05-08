"""
测试「猜你想问」功能：问「上月增长最快的是哪个店铺」
预期：返回的追问建议应包含「销售额」「订单量」等候选指标相关的追问
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 打开智能问数页面
    page.goto('http://localhost:3001')
    page.wait_for_load_state('networkidle')

    # 截图查看初始状态
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/dev_metric/test_output/01_initial.png', full_page=True)

    # 找到输入框并输入问题
    # 查找文本输入框
    input_selector = 'textarea[placeholder*="问数"], input[placeholder*="问数"], .chat-input textarea'
    page.wait_for_selector(input_selector, timeout=10000)
    page.fill(input_selector, '上月增长最快的是哪个店铺')
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/dev_metric/test_output/02_filled.png', full_page=True)

    # 点击发送按钮
    send_button = page.locator('button:has-text("发送"), button:has-text("问"), .send-btn').first
    send_button.click()

    # 等待回复出现
    page.wait_for_timeout(3000)
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/dev_metric/test_output/03_after_send.png', full_page=True)

    # 获取页面内容，查找回复和建议
    content = page.content()

    # 尝试找到回复和建议
    suggest_elements = page.locator('text=/销售额|订单量|访客数|增长最快/').all()
    if suggest_elements:
        print(f"✅ 找到相关建议:")
        for el in suggest_elements:
            print(f"  - {el.inner_text()}")
    else:
        print("❌ 未找到「销售额」「订单量」等候选指标相关的追问")

    # 打印回复内容
    messages = page.locator('.message, .chat-message, [class*="message"]').all()
    for msg in messages[-5:]:
        text = msg.inner_text()
        if text and len(text) > 5:
            print(f"\n回复内容: {text[:200]}")

    # 获取 suggest_questions 相关内容
    page.wait_for_timeout(1000)
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/dev_metric/test_output/04_final.png', full_page=True)

    # 打印 suggest 相关文本
    suggest_texts = page.locator('text=/suggest|追问|建议/').all()
    for s in suggest_texts:
        print(f"建议文本: {s.inner_text()[:100]}")

    browser.close()
    print("\n测试完成")