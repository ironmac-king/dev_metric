"""检查 rawMarkdown 的完整内容"""
from playwright.sync_api import sync_playwright
import sys

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto('http://localhost:3001/analysis')
    page.wait_for_load_state('networkidle')

    textarea = page.locator('textarea')
    if textarea.count() > 0:
        textarea.fill('分析近30天广告')
        send_btn = page.locator('.send-btn')
        if send_btn.count() > 0:
            send_btn.click()
            page.wait_for_timeout(60000)

            # 获取 rawMarkdown 的内容
            result = page.evaluate("""
                () => {
                    // 尝试从 Vue 实例获取
                    const app = document.querySelector('#app').__vue_app__;
                    if (app && app._instance) {
                        const proxy = app._instance.proxy;
                        if (proxy.$data && proxy.$data.rawMarkdown) {
                            return proxy.$data.rawMarkdown;
                        }
                        // 尝试其他方式
                        for (const key in proxy) {
                            if (proxy[key] && proxy[key].rawMarkdown) {
                                return proxy[key].rawMarkdown;
                            }
                        }
                    }
                    return null;
                }
            """)

            if result:
                print(f"rawMarkdown 长度: {len(result)}")
                print("\n=== rawMarkdown 内容 (前2000字符) ===")
                print(result[:2000])
            else:
                print("无法获取 rawMarkdown")

    browser.close()
