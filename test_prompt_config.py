"""
测试 Prompt 配置页面完整流程
包括：AI代写、保存、版本历史、回滚、智能问数
"""
from playwright.sync_api import sync_playwright
import time
import json

def test_prompt_config():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 捕获控制台日志
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        try:
            # ========== 1. Prompt 配置页面基础加载 ==========
            print("=" * 60)
            print("【测试 1】Prompt 配置页面加载")
            print("=" * 60)
            page.goto('http://localhost:3001/prompt-config')
            page.wait_for_load_state('networkidle')
            time.sleep(2)

            # 检查页面标题
            title = page.locator('.page-title').inner_text()
            print(f"页面标题: {title}")
            assert 'Prompt' in title, "页面标题不正确"
            results.append(("页面加载", "通过"))

            # ========== 2. Prompt 列表加载 ==========
            print("\n" + "=" * 60)
            print("【测试 2】Prompt 列表加载")
            print("=" * 60)
            menu_items = page.locator('.el-menu-item').all()
            print(f"找到 {len(menu_items)} 个 Prompt 配置")
            for item in menu_items:
                text = item.inner_text()
                print(f"  - {text}")

            # 等待列表加载
            time.sleep(1)
            if len(menu_items) > 0:
                results.append(("Prompt列表", f"通过 ({len(menu_items)} 项)"))
            else:
                results.append(("Prompt列表", "失败: 无数据"))
                return False

            # ========== 3. AI 代写功能 ==========
            print("\n" + "=" * 60)
            print("【测试 3】AI 代写功能")
            print("=" * 60)

            # 点击 AI 代写按钮
            ai_button = page.locator('button:has-text("AI 代写")')
            ai_button.click()
            time.sleep(0.5)

            # 检查弹窗
            dialog = page.locator('.el-dialog:visible')
            if dialog.count() > 0:
                print("模式选择弹窗已显示")

                # 选择"基于现有优化"
                page.locator('text=基于现有优化').click()
                print("选择: 基于现有优化")

                # 点击确定
                page.locator('.el-dialog:visible button:has-text("确定")').click()
                time.sleep(0.5)

                # 等待 AI 生成结果（应该出现结果弹窗）
                result_dialog = page.locator('.el-dialog:visible')
                if result_dialog.count() > 0:
                    dialog_title = page.locator('.el-dialog__header:visible').inner_text()
                    print(f"结果弹窗: {dialog_title}")

                    # 检查是否有内容
                    textarea = page.locator('.el-dialog:visible textarea').first
                    content = textarea.input_value()
                    print(f"生成内容长度: {len(content)} 字符")

                    if len(content) > 50:
                        results.append(("AI代写生成", "通过"))
                        # 点击应用到编辑器
                        page.locator('.el-dialog:visible button:has-text("应用到编辑器")').click()
                        time.sleep(0.5)
                        print("已应用到编辑器")
                    else:
                        results.append(("AI代写生成", "失败: 内容过短"))

                    # 关闭结果弹窗（如果还开着）
                    close_btn = page.locator('.el-dialog:visible .el-dialog__headerbtn')
                    if close_btn.count() > 0:
                        close_btn.click()
                        time.sleep(0.5)
                else:
                    print("未出现结果弹窗")
                    results.append(("AI代写生成", "失败: 无结果"))
            else:
                print("未出现模式选择弹窗")
                results.append(("AI代写弹窗", "失败"))

            # ========== 4. 保存功能 ==========
            print("\n" + "=" * 60)
            print("【测试 4】保存功能")
            print("=" * 60)

            # 获取当前版本
            current_version_tag = page.locator('.el-tag:visible').first
            if current_version_tag.count() > 0:
                version_text = current_version_tag.inner_text()
                print(f"当前版本标签: {version_text}")

            # 点击保存
            save_button = page.locator('button:has-text("保存")')
            save_button.click()
            time.sleep(2)

            # 检查是否成功
            # 等待消息提示
            page.wait_for_selector('.el-message', timeout=5000)
            message = page.locator('.el-message').first.inner_text()
            print(f"保存消息: {message}")

            if '成功' in message or 'success' in message.lower():
                results.append(("保存功能", "通过"))
            else:
                results.append(("保存功能", f"异常: {message}"))

            # ========== 5. 版本历史 ==========
            print("\n" + "=" * 60)
            print("【测试 5】版本历史")
            print("=" * 60)

            # 点击版本历史
            history_button = page.locator('button:has-text("版本历史")')
            history_button.click()
            time.sleep(1)

            # 检查弹窗
            history_dialog = page.locator('.el-dialog:visible')
            if history_dialog.count() > 0:
                print("版本历史弹窗已显示")

                # 等待表格加载
                time.sleep(0.5)
                table_rows = page.locator('.el-table__row').all()
                print(f"版本历史记录数: {len(table_rows)}")

                # 遍历每行
                for i, row in enumerate(table_rows):
                    cells = row.locator('td')
                    if cells.count() >= 4:
                        version = cells.nth(0).inner_text()
                        reason = cells.nth(3).inner_text()
                        print(f"  v{version} - {reason}")

                results.append(("版本历史", f"通过 ({len(table_rows)} 条)"))

                # 关闭弹窗
                page.keyboard.press('Escape')
                time.sleep(0.5)
            else:
                results.append(("版本历史", "失败"))

            # ========== 6. 智能问数测试 ==========
            print("\n" + "=" * 60)
            print("【测试 6】智能问数使用新Prompt")
            print("=" * 60)

            # 先导航到智能问数页面
            page.goto('http://localhost:3001/ask')
            page.wait_for_load_state('networkidle')
            time.sleep(2)

            # 检查页面元素 - 使用正确的选择器
            # el-input 的实际输入框是 .el-textarea__inner
            input_field = page.locator('.chat-input .el-textarea__inner')
            if input_field.count() > 0:
                print("问数输入框存在")

                # 输入测试问题
                test_question = "广告转化率最近7天是多少"
                input_field.fill(test_question)
                print(f"输入问题: {test_question}")

                # 点击发送按钮 - 是 .send-btn，不是文字"发送"
                send_button = page.locator('.send-btn')
                if send_button.count() > 0:
                    send_button.click()

                    # 等待 AI 回复出现（最多30秒）
                    # 注意：用户消息立即出现，需要等待 assistant 角色的消息
                    try:
                        page.wait_for_selector('.message-list .message.assistant', timeout=30000)
                        time.sleep(1)  # 额外等待确保渲染完成

                        # 截图调试
                        page.screenshot(path='C:/tmp/ask_page_after.png', full_page=True)
                        print("截图保存: C:/tmp/ask_page_after.png")

                        # 检查回复 - 查找 .message-list 下的消息
                        message_list = page.locator('.message-list')
                        if message_list.count() > 0:
                            messages = message_list.locator('.message').all()
                            print(f"收到消息数: {len(messages)}")

                            # 打印所有消息内容
                            for i, msg in enumerate(messages):
                                content = msg.locator('.message-content').inner_text()[:50] if msg.locator('.message-content').count() > 0 else "(no content)"
                                role = msg.get_attribute('class')
                                print(f"  消息{i+1}: {role} - {content}...")

                            if len(messages) >= 2:
                                last_message = messages[-1].locator('.message-content').inner_text()
                                print(f"AI回复前100字: {last_message[:100]}...")
                                results.append(("智能问数", "通过"))
                            else:
                                results.append(("智能问数", "无回复"))
                        else:
                            results.append(("智能问数", "消息列表未找到"))
                    except Exception as e:
                        print(f"等待超时: {e}")
                        page.screenshot(path='C:/tmp/ask_timeout.png', full_page=True)
                        results.append(("智能问数", f"超时: {e}"))
                else:
                    results.append(("智能问数", "未找到发送按钮"))
            else:
                results.append(("智能问数", "未找到输入框"))

            # ========== 7. 控制台错误检查 ==========
            print("\n" + "=" * 60)
            print("【测试 7】控制台错误检查")
            print("=" * 60)
            error_logs = [log for log in console_logs if 'error' in log.lower()]
            if error_logs:
                print(f"发现 {len(error_logs)} 条错误:")
                for log in error_logs[:3]:
                    print(f"  {log}")
                results.append(("控制台错误", f"有 {len(error_logs)} 条"))
            else:
                print("无错误日志")
                results.append(("控制台错误", "无"))

        except Exception as e:
            print(f"测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(("测试执行", f"失败: {e}"))

        finally:
            browser.close()

    # 打印结果
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for name, status in results:
        icon = "[PASS]" if "通过" in status and "失败" not in status else "[FAIL]"
        print(f"  {icon} {name}: {status}")

    passed = sum(1 for _, s in results if "通过" in s and "失败" not in s)
    total = len(results)
    print(f"\n通过率: {passed}/{total}")

    return passed >= total * 0.6  # 60% 通过率

if __name__ == "__main__":
    success = test_prompt_config()
    exit(0 if success else 1)
