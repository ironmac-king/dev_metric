/**
 * E2E 测试: 前端引擎切换 UI
 *
 * 运行方式:
 *   npx playwright test tests/e2e/ask.spec.js
 *
 * 前提条件:
 *   1. 启动前端: cd web && npm run dev
 *   2. 启动后端: python -m uvicorn ai.main:app --port 8081
 */

const { test, expect } = require('@playwright/test');

test.describe('智能问数 - 引擎切换', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/ask');
    // 等待页面加载
    await page.waitForLoadState('networkidle');
  });

  test('引擎切换按钮存在且可点击', async ({ page }) => {
    // 验证 Legacy 按钮存在
    const legacyBtn = page.locator('.engine-btn:has-text("Legacy")');
    await expect(legacyBtn).toBeVisible();

    // 验证 LangGraph 按钮存在
    const langgraphBtn = page.locator('.engine-btn:has-text("LangGraph")');
    await expect(langgraphBtn).toBeVisible();

    // 默认 Legacy 是激活状态
    await expect(legacyBtn).toHaveClass(/active/);
  });

  test('切换到 LangGraph 后按钮状态正确', async ({ page }) => {
    const langgraphBtn = page.locator('.engine-btn:has-text("LangGraph")');

    // 点击 LangGraph
    await langgraphBtn.click();

    // 验证 LangGraph 按钮激活
    await expect(langgraphBtn).toHaveClass(/active/);

    // 验证 Legacy 按钮不激活
    const legacyBtn = page.locator('.engine-btn:has-text("Legacy")');
    await expect(legacyBtn).not.toHaveClass(/active/);
  });

  test('引擎选择持久化到 localStorage', async ({ page }) => {
    const langgraphBtn = page.locator('.engine-btn:has-text("LangGraph")');

    // 切换到 LangGraph
    await langgraphBtn.click();

    // 验证 localStorage
    const engineType = await page.evaluate(() => localStorage.getItem('engine_type'));
    expect(engineType).toBe('langgraph');
  });

  test('刷新后保持引擎选择', async ({ page }) => {
    const langgraphBtn = page.locator('.engine-btn:has-text("LangGraph")');

    // 切换到 LangGraph
    await langgraphBtn.click();

    // 刷新页面
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 验证仍然选中 LangGraph
    await expect(langgraphBtn).toHaveClass(/active/);
  });

  test('切换引擎后可以正常提问', async ({ page }) => {
    const langgraphBtn = page.locator('.engine-btn:has-text("LangGraph")');
    const legacyBtn = page.locator('.engine-btn:has-text("Legacy")');
    const input = page.locator('textarea').first();

    // 切换到 Legacy 并提问
    await legacyBtn.click();
    await input.fill('本月销售额是多少');
    await page.keyboard.press('Enter');

    // 等待响应
    await page.waitForSelector('.message.assistant', { timeout: 10000 });

    // 验证消息出现
    const messages = page.locator('.message.assistant');
    await expect(messages.first()).toBeVisible();

    // 切换到 LangGraph 并提问
    await langgraphBtn.click();
    await input.fill('本月销售额是多少');
    await page.keyboard.press('Enter');

    // 等待响应
    await page.waitForSelector('.message.assistant:nth-child(4)', { timeout: 10000 });

    // 验证第二条回复出现
    const allMessages = page.locator('.message.assistant');
    const count = await allMessages.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });
});
