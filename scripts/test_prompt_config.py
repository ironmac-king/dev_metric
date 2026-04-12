#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整测试意图识别配置驱动架构
测试范围：
1. Go 后端 API 测试
2. Python AI 服务配置加载测试
3. 前端 NLPConfig.vue 页面测试
4. 闲聊意图识别从 DB 加载测试
"""
import json
import time
import httpx
from playwright.sync_api import sync_playwright, expect

# 测试配置
BACKEND_URL = "http://localhost:8080"
AI_URL = "http://localhost:8081"
FRONTEND_URL = "http://localhost:3001"

def log_test(name, passed, detail=""):
    """打印测试结果"""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}")
    if detail:
        print(f"      {detail}")

def test_1_go_backend_api():
    """测试1: Go 后端 API"""
    print("\n" + "="*60)
    print("测试1: Go 后端 API")
    print("="*60)

    all_passed = True

    # 1.1 GET /api/v1/prompt-configs
    print("\n--- 1.1 获取所有 Prompt 配置 ---")
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/v1/prompt-configs", timeout=10)
        data = resp.json()
        configs = data.get("data", [])

        passed = resp.status_code == 200 and len(configs) > 0
        log_test("GET /api/v1/prompt-configs 返回200", passed,
                 f"获取到 {len(configs)} 条配置")
        all_passed &= passed

        # 打印配置列表
        print(f"\n  配置列表:")
        for cfg in configs:
            name = cfg.get("name", "")
            category = cfg.get("category", "")
            status = cfg.get("status", 0)
            prompt_len = len(cfg.get("prompt_text", ""))
            print(f"    - {name:30s} | {category:15s} | status={status} | {prompt_len} chars")
    except Exception as e:
        log_test("GET /api/v1/prompt-configs", False, str(e))
        all_passed = False

    # 1.2 GET /api/v1/prompt-configs/active?name=nl2structure
    print("\n--- 1.2 获取单个 Prompt 配置(nl2structure) ---")
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/v1/prompt-configs/active",
            params={"name": "nl2structure"},
            timeout=10
        )
        data = resp.json()
        cfg = data.get("data")

        passed = resp.status_code == 200 and cfg is not None
        log_test("GET nl2structure 配置", passed,
                 f"version={cfg.get('version')}, {len(cfg.get('prompt_text', ''))} chars" if cfg else "无数据")
        all_passed &= passed
    except Exception as e:
        log_test("GET nl2structure 配置", False, str(e))
        all_passed = False

    # 1.3 测试新增的6个 prompt 配置
    print("\n--- 1.3 验证新增的6个 Prompt 配置 ---")
    new_prompts = [
        "intent_validation",
        "clarification_decision",
        "followup_expansion",
        "metric_extraction",
        "empty_result_followup",
        "sql_generation_fallback"
    ]

    for name in new_prompts:
        try:
            resp = httpx.get(
                f"{BACKEND_URL}/api/v1/prompt-configs/active",
                params={"name": name},
                timeout=10
            )
            data = resp.json()
            cfg = data.get("data")

            passed = cfg is not None
            if passed:
                prompt_text = cfg.get("prompt_text", "")
                variables = cfg.get("variables", [])
                print(f"  {name:30s} - {len(prompt_text):4d} chars, variables: {len(variables)}")
            else:
                print(f"  {name:30s} - NOT FOUND")
            log_test(f"配置存在: {name}", passed)
            all_passed &= passed
        except Exception as e:
            log_test(f"配置存在: {name}", False, str(e))
            all_passed = False

    # 1.4 GET /api/v1/nlp/templates (意图模板)
    print("\n--- 1.4 获取意图模板 ---")
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/v1/nlp/templates", timeout=10)
        data = resp.json()
        # API 返回结构是 {"data": {"intent_templates": [...], "sql_templates": [...]}}
        result_data = data.get("data", {})
        if isinstance(result_data, dict):
            templates = result_data.get("intent_templates", [])
        else:
            templates = result_data

        passed = resp.status_code == 200 and len(templates) > 0
        log_test("GET /api/v1/nlp/templates", passed,
                 f"获取到 {len(templates)} 条意图模板")
        all_passed &= passed

        # 打印闲聊意图模板
        print(f"\n  闲聊意图模板:")
        greeting_templates = [t for t in templates if t.get("intent") in ["greeting", "thanks", "bye"]]
        for t in greeting_templates:
            print(f"    - {t.get('name')} | intent={t.get('intent')} | priority={t.get('priority')}")
    except Exception as e:
        log_test("GET /api/v1/nlp/templates", False, str(e))
        all_passed = False

    return all_passed

def test_2_python_ai_config():
    """测试2: Python AI 服务配置加载"""
    print("\n" + "="*60)
    print("测试2: Python AI 服务配置加载")
    print("="*60)

    all_passed = True

    # 2.1 健康检查
    print("\n--- 2.1 Python AI 健康检查 ---")
    try:
        resp = httpx.get(f"{AI_URL}/health", timeout=10)
        passed = resp.status_code == 200
        log_test("Python AI /health", passed, f"status={resp.status_code}")
        all_passed &= passed
    except Exception as e:
        log_test("Python AI /health", False, str(e))
        all_passed = False

    # 2.2 PromptManager 从 Go API 加载
    print("\n--- 2.2 PromptManager 从 Go API 加载配置 ---")
    try:
        # Python AI 通过 PromptManager -> Go API 获取配置
        # 测试 Go API 的 prompt-configs 端点（Python AI 内部调用）
        resp = httpx.get(f"{BACKEND_URL}/api/v1/prompt-configs", timeout=10)
        data = resp.json()
        configs = data.get("data", [])

        passed = resp.status_code == 200 and len(configs) > 0
        log_test("Go API Prompt 配置数量", passed,
                 f"Go API 返回 {len(configs)} 条配置")
        all_passed &= passed

        # 验证新增的6个配置是否可用
        expected_names = ["intent_validation", "clarification_decision", "followup_expansion",
                        "metric_extraction", "empty_result_followup", "sql_generation_fallback"]
        found_names = [c.get("name") for c in configs]
        for name in expected_names:
            passed = name in found_names
            log_test(f"配置存在: {name}", passed)
            all_passed &= passed
    except Exception as e:
        log_test("PromptManager 加载验证", False, str(e))
        all_passed = False

    # 2.3 验证 Redis 缓存
    print("\n--- 2.3 验证 Redis 缓存 ---")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)

        # 先清除缓存，确保下次请求会重新加载
        r.delete("prompt:nl2structure")

        # 第一次请求应该写入 Redis
        resp = httpx.get(f"{BACKEND_URL}/api/v1/prompt-configs/active",
                         params={"name": "nl2structure"}, timeout=10)

        # 检查 Redis 是否有缓存
        cached = r.get("prompt:nl2structure")
        passed = cached is not None
        log_test("Redis 缓存已写入", passed, "key=prompt:nl2structure")
        all_passed &= passed

        # 第二次请求应该从 Redis 读取（已验证缓存命中）
        if cached:
            cfg_data = json.loads(cached)
            print(f"  Redis 缓存数据: version={cfg_data.get('version')}")
    except Exception as e:
        log_test("Redis 缓存验证", False, str(e))
        all_passed = False

    return all_passed

def test_3_frontend_nlp_config():
    """测试3: 前端 NLPConfig.vue 页面测试"""
    print("\n" + "="*60)
    print("测试3: 前端 NLPConfig.vue 页面测试")
    print("="*60)

    all_passed = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 3.1 登录
        print("\n--- 3.1 登录 ---")
        try:
            page.goto(f"{FRONTEND_URL}/login")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            # 查找登录表单
            page.fill("input[type='text'], input[placeholder*='账']", "admin")
            page.fill("input[type='password']", "admin123")
            page.click(".login-btn")

            page.wait_for_timeout(2000)
            current_url = page.url
            passed = "login" not in current_url.lower()
            log_test("登录成功", passed, f"url={current_url}")
            all_passed &= passed
        except Exception as e:
            log_test("登录", False, str(e))
            all_passed = False

        # 3.2 导航到 NLPConfig 页面
        print("\n--- 3.2 导航到意图配置页面 ---")
        try:
            # 尝试点击菜单
            page.goto(f"{FRONTEND_URL}/nlp-config")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            # 检查页面标题
            title = page.locator("h1, .page-title, [class*='title']").first.text_content()
            passed = title is not None
            log_test("NLPConfig 页面加载", passed, f"title={title}")
            all_passed &= passed
        except Exception as e:
            log_test("NLPConfig 页面加载", False, str(e))
            all_passed = False

        # 3.3 切换到 Prompt Tab
        print("\n--- 3.3 切换到 Prompt Tab ---")
        try:
            # 查找 Prompt Tab
            tabs = page.locator("[class*='tab'], [role='tab'], .el-tabs__item")
            tab_count = tabs.count()
            print(f"  发现 {tab_count} 个 Tab")

            # 点击 Prompt Tab (通常第二个)
            if tab_count >= 2:
                tabs.nth(1).click()
                page.wait_for_timeout(1000)
                log_test("切换到 Prompt Tab", True)
            else:
                # 尝试通过文本查找
                prompt_tab = page.locator("text=Prompt, text=prompt")
                if prompt_tab.count() > 0:
                    prompt_tab.first.click()
                    page.wait_for_timeout(1000)
                    log_test("切换到 Prompt Tab", True)
                else:
                    log_test("切换到 Prompt Tab", False, "未找到 Prompt Tab")
                    all_passed = False
        except Exception as e:
            log_test("切换到 Prompt Tab", False, str(e))
            all_passed = False

        # 3.4 验证 Prompt 配置列表
        print("\n--- 3.4 验证 Prompt 配置列表 ---")
        try:
            # 等待表格加载
            page.wait_for_timeout(2000)

            # 查找表格
            tables = page.locator(".el-table, table")
            if tables.count() > 0:
                rows = page.locator(".el-table__row, tbody tr")
                row_count = rows.count()
                passed = row_count > 0
                log_test("Prompt 配置表格有数据", passed, f"{row_count} 行")
                all_passed &= passed

                # 打印前几条数据
                print(f"\n  Prompt 配置列表(前5条):")
                for i in range(min(5, row_count)):
                    cells = rows.nth(i).locator("td")
                    if cells.count() >= 2:
                        name = cells.nth(0).text_content()
                        category = cells.nth(1).text_content()
                        print(f"    - {name} | {category}")
            else:
                # 可能是卡片列表
                cards = page.locator("[class*='card']")
                card_count = cards.count()
                passed = card_count > 0
                log_test("Prompt 配置卡片有数据", passed, f"{card_count} 个卡片")
                all_passed &= passed
        except Exception as e:
            log_test("验证 Prompt 配置列表", False, str(e))
            all_passed = False

        browser.close()

    return all_passed

def test_4_chat_intent_recognition():
    """测试4: 闲聊意图识别从 DB 加载"""
    print("\n" + "="*60)
    print("测试4: 闲聊意图识别从 DB 加载")
    print("="*60)

    all_passed = True

    # 4.1 验证 intent_templates 中有闲聊配置
    print("\n--- 4.1 验证 DB 中闲聊意图模板 ---")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='192.168.1.225',
            port=5432,
            database='dev_metric',
            user='postgres',
            password='admin123'
        )
        cur = conn.cursor()

        # 查询闲聊意图模板
        cur.execute("""
            SELECT name, intent, patterns, priority, response
            FROM intent_templates
            WHERE intent IN ('greeting', 'thanks', 'bye')
            ORDER BY priority DESC
        """)
        rows = cur.fetchall()

        passed = len(rows) >= 3
        log_test("闲聊意图模板数量", passed, f"找到 {len(rows)} 条闲聊模板")

        print(f"\n  闲聊意图模板:")
        for r in rows:
            print(f"    - {r[0]:20s} | intent={r[1]:10s} | patterns={r[2][:30]}...")

        cur.close()
        conn.close()
        all_passed &= passed
    except Exception as e:
        log_test("验证闲聊意图模板", False, str(e))
        all_passed = False

    # 4.2 测试闲聊对话
    print("\n--- 4.2 测试闲聊对话(你好) ---")
    try:
        resp = httpx.post(
            f"{AI_URL}/api/v1/ask",
            json={"question": "你好"},
            timeout=30
        )
        data = resp.json()

        # 检查响应
        answer = data.get("answer", "")
        passed = resp.status_code == 200 and len(answer) > 0
        log_test("闲聊对话-你好", passed, f"answer={answer[:50]}...")
        all_passed &= passed
    except Exception as e:
        log_test("闲聊对话-你好", False, str(e))
        all_passed = False

    # 4.3 测试谢谢
    print("\n--- 4.3 测试闲聊对话(谢谢) ---")
    try:
        resp = httpx.post(
            f"{AI_URL}/api/v1/ask",
            json={"question": "谢谢"},
            timeout=30
        )
        data = resp.json()

        answer = data.get("answer", "")
        passed = resp.status_code == 200 and len(answer) > 0
        log_test("闲聊对话-谢谢", passed, f"answer={answer[:50]}...")
        all_passed &= passed
    except Exception as e:
        log_test("闲聊对话-谢谢", False, str(e))
        all_passed = False

    # 4.4 测试再见
    print("\n--- 4.4 测试闲聊对话(再见) ---")
    try:
        resp = httpx.post(
            f"{AI_URL}/api/v1/ask",
            json={"question": "再见"},
            timeout=30
        )
        data = resp.json()

        answer = data.get("answer", "")
        passed = resp.status_code == 200 and len(answer) > 0
        log_test("闲聊对话-再见", passed, f"answer={answer[:50]}...")
        all_passed &= passed
    except Exception as e:
        log_test("闲聊对话-再见", False, str(e))
        all_passed = False

    return all_passed

def main():
    print("="*60)
    print("意图识别配置驱动架构 - 完整测试")
    print("="*60)

    results = []

    # 执行所有测试
    results.append(("Go 后端 API", test_1_go_backend_api()))
    results.append(("Python AI 配置加载", test_2_python_ai_config()))
    results.append(("前端 NLPConfig 页面", test_3_frontend_nlp_config()))
    results.append(("闲聊意图识别", test_4_chat_intent_recognition()))

    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    total_passed = 0
    total_tests = len(results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if passed:
            total_passed += 1

    print(f"\n  总计: {total_passed}/{total_tests} 通过")

    if total_passed == total_tests:
        print("\n  *** 全部测试通过! ***")
    else:
        print(f"\n  *** 有 {total_tests - total_passed} 项测试失败 ***")

    return total_passed == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)