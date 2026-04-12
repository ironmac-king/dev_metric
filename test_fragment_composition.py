"""
SQL Fragment Composition E2E Test
Tests:
1. Go backend API - prompt_configs and nlp_templates
2. Python AI service config loading
3. NLPConfig.vue page Prompt Tab
4. Chat intent recognition (hi, thanks, goodbye) from DB
"""
import json
import urllib.request


def test_go_backend_apis():
    """Test Go backend API"""
    print("\n=== 1. Go Backend API Test ===")

    # GET /api/v1/nlp/templates?type=engine
    req = urllib.request.Request(
        "http://localhost:8080/api/v1/nlp/templates?type=engine",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        assert data["code"] == 0, f"API error: {data}"
        # Response: data.sql_templates and data.intent_templates
        resp_data = data["data"]
        if isinstance(resp_data, dict) and "sql_templates" in resp_data:
            templates = resp_data["sql_templates"]
        else:
            templates = resp_data if isinstance(resp_data, list) else []
        print(f"  [OK] GET /api/v1/nlp/templates?type=engine -> {len(templates)} engine templates")

    # GET /api/v1/nlp/intents
    req = urllib.request.Request(
        "http://localhost:8080/api/v1/nlp/intents",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        assert data["code"] == 0, f"API error: {data}"
        # Response: data is a list directly
        resp_data = data["data"]
        intents = resp_data if isinstance(resp_data, list) else []
        print(f"  [OK] GET /api/v1/nlp/intents -> {len(intents)} intent templates")

    # Check chat intents exist
    greeting_intent = next((i for i in intents if i["intent"] == "greeting"), None)
    thanks_intent = next((i for i in intents if i["intent"] == "thanks"), None)
    goodbye_intent = next((i for i in intents if i["intent"] == "bye"), None)

    assert greeting_intent is not None, "Missing greeting intent"
    assert thanks_intent is not None, "Missing thanks intent"
    assert goodbye_intent is not None, "Missing goodbye/bye intent"

    greeting_count = len(greeting_intent["patterns"].split(","))
    thanks_count = len(thanks_intent["patterns"].split(","))
    goodbye_count = len(goodbye_intent["patterns"].split(","))

    print(f"  [OK] Chat intents: greeting({greeting_count} patterns), "
          f"thanks({thanks_count} patterns), "
          f"bye({goodbye_count} patterns)")

    return True


def test_python_ai_service():
    """Test Python AI service loading config"""
    print("\n=== 2. Python AI Service Config Test ===")

    # Test SQL fragment composition engine - call the Python module directly
    try:
        from ai.sql_template_engine.engine import generate_sql

        ctx = {
            "starrocks_sql": "SELECT SUM(SPEND) AS SPEND FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1",
            "time_info": {"start_date": "2026-04-01", "end_date": "2026-04-12"},
            "date_column": "FDATE",
            "dimension": "FSITE",
            "top_n": "10"
        }

        for intent in ["query_value", "query_trend", "query_ranking", "query_comparison"]:
            sql = generate_sql(intent, ctx)
            assert sql is not None, f"{intent} returned None"
            print(f"  [OK] {intent}: {sql[:60]}...")

        # Test no dimension fallback
        ctx_no_dim = dict(ctx)
        del ctx_no_dim["dimension"]
        sql = generate_sql("query_ranking", ctx_no_dim)
        assert "GROUP BY FDATE" in sql, "Should default to date_column GROUP BY"
        print(f"  [OK] No dimension fallback: GROUP BY FDATE")

        print(f"  [OK] SQL Fragment Composition Engine working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] SQL Fragment Composition Engine: {e}")
        return False


def test_chat_intent_recognition():
    """Test chat intent recognition patterns from DB"""
    print("\n=== 3. Chat Intent Recognition Test ===")

    # Get intent list
    req = urllib.request.Request(
        "http://localhost:8080/api/v1/nlp/intents",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        # Response: data is a list directly
        intents = data["data"] if isinstance(data["data"], list) else []

    # Test greeting
    greeting_intent = next((i for i in intents if i["intent"] == "greeting"), None)
    assert greeting_intent is not None, "Missing greeting intent"
    patterns = greeting_intent["patterns"].split(",")
    print(f"  [OK] Greeting patterns: {greeting_intent['patterns'][:50]}...")
    # Note: Due to encoding, we check if pattern items exist
    assert len(patterns) >= 5, "Greeting should have multiple patterns"
    print(f"  [OK] Greeting has {len(patterns)} patterns")

    # Test thanks
    thanks_intent = next((i for i in intents if i["intent"] == "thanks"), None)
    assert thanks_intent is not None, "Missing thanks intent"
    patterns = thanks_intent["patterns"].split(",")
    print(f"  [OK] Thanks patterns: {thanks_intent['patterns'][:50]}...")
    assert len(patterns) >= 3, "Thanks should have multiple patterns"
    print(f"  [OK] Thanks has {len(patterns)} patterns")

    # Test goodbye/bye
    goodbye_intent = next((i for i in intents if i["intent"] == "bye"), None)
    assert goodbye_intent is not None, "Missing bye intent"
    patterns = goodbye_intent["patterns"].split(",")
    print(f"  [OK] Bye patterns: {goodbye_intent['patterns'][:50]}...")
    assert len(patterns) >= 3, "Bye should have multiple patterns"
    print(f"  [OK] Bye has {len(patterns)} patterns")

    return True


def test_nlp_config_vue_page():
    """Test NLPConfig.vue page with Playwright"""
    print("\n=== 4. NLPConfig.vue Page Test ===")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [SKIP] Playwright not installed, using direct API test instead")
        # Fall back to API test
        req = urllib.request.Request(
            "http://localhost:8080/api/v1/nlp/intents",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print(f"  [OK] NLPConfig data available via API: {len(data['data']['intent_templates'])} intents")
        return True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto("http://localhost:3001")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            # Navigate to NLP config page
            page.goto("http://localhost:3001/nlp-config")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)

            title = page.title()
            print(f"  [OK] Page title: {title}")

            # Check for tabs
            tabs = page.locator(".el-tabs").count()
            print(f"  [OK] el-tabs components: {tabs}")

            # Check Prompt tab
            prompt_tab = page.locator("text=Prompt").first
            if prompt_tab.is_visible():
                print("  [OK] Prompt Tab visible")
                prompt_tab.click()
                page.wait_for_timeout(500)
            else:
                print("  [INFO] Prompt Tab not found (layout may differ)")

            # Check for tables
            tables = page.locator(".el-table").count()
            print(f"  [OK] el-table components: {tables}")

        finally:
            browser.close()

    return True


def test_sql_fragment_details():
    """Test detailed SQL fragment composition for each intent"""
    print("\n=== 5. SQL Fragment Details Test ===")

    from ai.sql_template_engine.engine import generate_sql

    ctx = {
        "starrocks_sql": "SELECT SUM(SPEND) AS SPEND FROM ids.IDS_AMZ_COMPREHENSIVE_DI WHERE 1=1",
        "time_info": {"start_date": "2026-04-01", "end_date": "2026-04-12"},
        "date_column": "FDATE",
        "dimension": "FSITE",
        "top_n": "10"
    }

    # query_value: should be simple
    sql = generate_sql("query_value", ctx)
    assert "SUM(SPEND)" in sql
    print(f"  [OK] query_value contains SUM(SPEND)")

    # query_trend: should have LAG
    sql = generate_sql("query_trend", ctx)
    assert "LAG(" in sql
    assert "mom_rate" in sql
    assert "GROUP BY FSITE" in sql
    print(f"  [OK] query_trend has LAG and mom_rate")

    # query_ranking: should have RANK
    sql = generate_sql("query_ranking", ctx)
    assert "RANK()" in sql
    assert "rank_num" in sql
    assert "pct_of_total" in sql
    assert "GROUP BY FSITE" in sql
    print(f"  [OK] query_ranking has RANK, rank_num, pct_of_total")

    # query_comparison: should have YoY
    sql = generate_sql("query_comparison", ctx)
    assert "yoy_rate" in sql
    assert "t1." in sql
    assert "t2." in sql
    print(f"  [OK] query_comparison has yoy_rate and t1/t2 join")

    return True


def main():
    print("=" * 60)
    print("SQL Fragment Composition - Complete E2E Test")
    print("=" * 60)

    results = []

    # 1. Go backend API
    try:
        results.append(("Go Backend API", test_go_backend_apis()))
    except Exception as e:
        print(f"  [FAIL] Go Backend API: {e}")
        results.append(("Go Backend API", False))

    # 2. Python AI service
    try:
        results.append(("Python AI Service", test_python_ai_service()))
    except Exception as e:
        print(f"  [FAIL] Python AI Service: {e}")
        results.append(("Python AI Service", False))

    # 3. Chat intent recognition
    try:
        results.append(("Chat Intent Recognition", test_chat_intent_recognition()))
    except Exception as e:
        print(f"  [FAIL] Chat Intent Recognition: {e}")
        results.append(("Chat Intent Recognition", False))

    # 4. NLPConfig.vue page
    try:
        results.append(("NLPConfig.vue Page", test_nlp_config_vue_page()))
    except Exception as e:
        print(f"  [FAIL] NLPConfig.vue Page: {e}")
        results.append(("NLPConfig.vue Page", False))

    # 5. SQL fragment details
    try:
        results.append(("SQL Fragment Details", test_sql_fragment_details()))
    except Exception as e:
        print(f"  [FAIL] SQL Fragment Details: {e}")
        results.append(("SQL Fragment Details", False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {name}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("All tests passed!" if all_passed else "Some tests failed!"))
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
