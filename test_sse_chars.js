"""检查 SSE chunk 数据 - 修复版"""
from playwright.sync_api import sync_playwright
import sys

sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 存储所有 chunk 数据
    chunks = []

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

            # 等待一段时间后检查 chunks
            page.wait_for_timeout(5000)

            # 通过 evaluate 获取 chunks
            chunks_info = page.evaluate("""
                () => {
                    // 尝试从 Vue 实例获取 rawMarkdown
                    const app = document.querySelector('#app').__vue_app__;
                    if (app) {
                        // 找到 rawMarkdown 的值
                        const instances = app._instance?.proxy?.$data;
                        if (instances && instances.rawMarkdown) {
                            const text = instances.rawMarkdown;
                            // 返回前500字符
                            return text.substring(0, 500);
                        }
                    }
                    return 'not found';
                }
            """)

            print(f"\n=== rawMarkdown 前500字符 ===")
            print(chunks_info)

            # 查找 |  指标 的位置
            if '|  指标' in chunks_info:
                idx = chunks_info.indexOf('|  指标')
                print(f"\n'|  指标' 在位置 {idx}")
                print(f"前50字符: ...{chunks_info[max(0,idx-50):idx+50]}...")
            else:
                print("\n'|  指标' 未找到")

            page.wait_for_timeout(55000)

    browser.close()
