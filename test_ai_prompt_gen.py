"""
AI Prompt Generation Full Test
Test flow: Login -> Prompt Config -> AI Write -> Save Verification
"""
from playwright.sync_api import sync_playwright
import time

def test_ai_prompt_generation():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Enable console log capture
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # Enable network request/response capture
        api_requests = []
        page.on("request", lambda req: api_requests.append(f"REQUEST: {req.method} {req.url}") if "/prompt-configs" in req.url else None)
        page.on("response", lambda resp: api_requests.append(f"RESPONSE: {resp.status} {resp.url}") if "/prompt-configs" in resp.url else None)

        results = {
            "passed": [],
            "failed": []
        }

        try:
            # 1. Login
            print("1. Logging in...")
            page.goto('http://localhost:3002/login')
            page.wait_for_load_state('networkidle')
            page.fill('input[placeholder="用户名"]', 'admin')
            page.fill('input[placeholder="密码"]', 'admin123')
            page.click('button:has-text("登录")')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            print(f"   Current URL: {page.url}")

            # Check if we're on dashboard
            dashboard_visible = page.locator('text=指标管理').is_visible()
            if '/login' not in page.url or dashboard_visible:
                results["passed"].append("Login succeeded")
            else:
                results["failed"].append("Login failed")

            # 2. Go to Prompt config page
            print("2. Going to Prompt config page...")
            page.goto('http://localhost:3002/prompt-config')
            page.wait_for_load_state('networkidle')
            time.sleep(2)

            # Check if left list has configs
            menu_items = page.locator('.el-menu-item').all()
            print(f"   Found {len(menu_items)} Prompt configs")

            if len(menu_items) > 0:
                results["passed"].append("Prompt list loaded")

                # 3. Click on nl2structure config
                print("3. Selecting nl2structure config...")
                nl2structure_item = page.locator('.el-menu-item:has-text("nl2structure")').first
                nl2structure_item.click()
                page.wait_for_timeout(2000)

                # Check right edit area
                prompt_content = page.locator('textarea').first
                if prompt_content.is_visible():
                    results["passed"].append("Edit form displayed")
                    current_text = prompt_content.input_value()
                    print(f"   Current prompt length: {len(current_text)} chars")

                # 4. Click AI write button
                print("4. Clicking AI write button...")
                ai_button = page.locator('button:has-text("AI 代写")')
                page.wait_for_timeout(1000)
                if ai_button.is_visible():
                    ai_button.click()
                    time.sleep(1)

                    # 5. Check mode selection dialog
                    print("5. Checking mode selection dialog...")
                    dialog = page.locator('.el-dialog:visible')
                    if dialog.is_visible():
                        results["passed"].append("AI write dialog displayed")

                        # Select "improve" mode
                        improve_radio = page.locator('.el-radio:has-text("基于现有优化")')
                        if improve_radio.is_visible():
                            improve_radio.click()
                            results["passed"].append("Selected improve mode")

                        # Click confirm
                        print("6. Executing AI write...")
                        confirm_btn = dialog.locator('button:has-text("确定")')
                        confirm_btn.click()

                        # Wait for AI generation (may take time)
                        print("   Waiting for AI generation (60s)...")
                        page.wait_for_timeout(60000)

                        # Print captured logs
                        print(f"   Console logs captured: {len(console_logs)}")
                        for log in console_logs[-5:]:
                            print(f"     {log[:200]}")

                        print(f"   API requests captured: {len(api_requests)}")
                        for req in api_requests[-10:]:
                            print(f"     {req[:200]}")

                        # 7. Check result dialog
                        print("7. Checking AI generation result...")

                        # Check all visible dialogs
                        all_dialogs = page.locator('.el-dialog:visible').all()
                        print(f"   Visible dialogs: {len(all_dialogs)}")
                        for i, dlg in enumerate(all_dialogs):
                            title = dlg.locator('.el-dialog__header').text_content() if dlg.locator('.el-dialog__header').is_visible() else "No title"
                            print(f"     Dialog {i}: {title}")

                        result_dialog = page.locator('.el-dialog:visible')
                        if result_dialog.is_visible():
                            textarea = result_dialog.locator('textarea').first
                            if textarea.is_visible():
                                content = textarea.input_value()
                                print(f"   Generated content length: {len(content)} chars")
                                if len(content) > 100:
                                    results["passed"].append(f"AI generation succeeded with {len(content)} chars")
                                else:
                                    results["failed"].append("AI generation content too short")

                                # 8. Apply to editor
                                print("8. Applying to editor...")
                                apply_btn = result_dialog.locator('button:has-text("应用到编辑器")')
                                if apply_btn.is_visible():
                                    apply_btn.click()
                                    page.wait_for_timeout(1000)
                                    results["passed"].append("Applied to editor")
                                else:
                                    results["failed"].append("Apply button not found")
                            else:
                                results["failed"].append("Result textarea not found")
                        else:
                            # Dialog not visible - check if there's an error message
                            error_msg = page.locator('.el-message-error').first
                            if error_msg.is_visible():
                                error_text = error_msg.text_content()
                                results["failed"].append(f"AI generation error: {error_text}")
                            else:
                                results["failed"].append("Result dialog not shown")
                    else:
                        results["failed"].append("AI write dialog not shown")
                else:
                    results["failed"].append("AI write button not found")
            else:
                results["failed"].append("Prompt list is empty")

            # Take screenshot
            page.screenshot(path='C:/tmp/ai_prompt_test.png', full_page=True)
            print("   Screenshot saved to C:/tmp/ai_prompt_test.png")

        except Exception as e:
            results["failed"].append(f"Test exception: {str(e)}")
            print(f"   Exception: {e}")
            page.screenshot(path='C:/tmp/ai_prompt_error.png', full_page=True)

        finally:
            browser.close()

        # Output results
        print("\n" + "="*50)
        print("Test Results")
        print("="*50)
        print(f"Passed: {len(results['passed'])}")
        for item in results["passed"]:
            print(f"  [PASS] {item}")
        print(f"Failed: {len(results['failed'])}")
        for item in results["failed"]:
            print(f"  [FAIL] {item}")

        return len(results["failed"]) == 0

if __name__ == "__main__":
    success = test_ai_prompt_generation()
    exit(0 if success else 1)
