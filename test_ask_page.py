"""
探索智能问数页面结构
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 直接访问智能问数页面
    page.goto('http://localhost:3001/#/ask')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)  # 等待 Vue 渲染

    # 截图查看
    page.screenshot(path='C:/Users/4014/Desktop/dev_metric/dev_metric/test_output/01_ask_page.png', full_page=True)

    # 查找所有可见的文本
    body_text = page.locator('body').inner_text()
    print(f"Page text (first 500 chars):\n{body_text[:500]}")

    # 查找输入框
    inputs = page.locator('input, textarea').all()
    print(f"\nFound {len(inputs)} input fields:")
    for i, inp in enumerate(inputs):
        try:
            placeholder = inp.get_attribute('placeholder') or ""
            inp_type = inp.get_attribute('type') or "text"
            print(f"  [{i}] type={inp_type}, placeholder={placeholder}")
        except:
            pass

    # 查找按钮
    buttons = page.locator('button').all()
    print(f"\nFound {len(buttons)} buttons:")
    for i, btn in enumerate(buttons):
        try:
            text = btn.inner_text().strip()[:30]
            if text:
                print(f"  [{i}] {text}")
        except:
            pass

    browser.close()
    print("\nDone")