"""
探索智能问数页面的结构
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

    # 查找所有按钮和输入框
    buttons = page.locator('button').all()
    print(f"发现 {len(buttons)} 个按钮:")
    for btn in buttons[:10]:
        try:
            text = btn.inner_text()
            if text.strip():
                print(f"  按钮: {text.strip()[:50]}")
        except:
            pass

    inputs = page.locator('input, textarea').all()
    print(f"\n发现 {len(inputs)} 个输入框:")
    for inp in inputs[:10]:
        try:
            placeholder = inp.get_attribute('placeholder')
            print(f"  输入框 placeholder: {placeholder}")
        except:
            pass

    # 尝试导航到智能问数页面
    nav_links = page.locator('a, .menu-item, [class*="nav"], [class*="menu"]').all()
    print(f"\n发现 {len(nav_links)} 个导航元素:")
    for link in nav_links[:15]:
        try:
            text = link.inner_text()
            href = link.get_attribute('href')
            if text.strip():
                print(f"  导航: {text.strip()[:30]} -> {href}")
        except:
            pass

    # 查找"智能问数"相关文字
    ask_text = page.locator('text=/问数|Ask|NL2SQL|智能问答/').all()
    print(f"\n发现 {len(ask_text)} 个相关文字:")
    for t in ask_text[:5]:
        try:
            print(f"  {t.inner_text()[:50]}")
        except:
            pass

    browser.close()
    print("\n探索完成")