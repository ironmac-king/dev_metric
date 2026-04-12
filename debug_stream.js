const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // 捕获控制台日志
  const logs = [];
  page.on('console', msg => {
    if (msg.text().includes('[DEBUG]')) {
      logs.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    logs.push('PAGE ERROR: ' + err.message);
  });

  try {
    await page.goto('http://localhost:3001/analysis', { waitUntil: 'networkidle', timeout: 30000 });

    // 等待页面加载
    await page.waitForTimeout(2000);

    // 输入查询
    const input = page.locator('textarea').first();
    await input.fill('分析近30天广告');
    await input.press('Enter');

    // 等待流式完成（最多60秒）
    await page.waitForTimeout(60000);

    // 获取结果内容
    const resultText = await page.locator('.result-text').textContent().catch(() => 'N/A');
    console.log('=== RESULT TEXT (first 500 chars) ===');
    console.log(resultText.substring(0, 500));

    console.log('\n=== DEBUG LOGS ===');
    logs.forEach(log => console.log(log));

  } catch (e) {
    console.error('Test error:', e.message);
    console.log('\n=== DEBUG LOGS ===');
    logs.forEach(log => console.log(log));
  }

  await browser.close();
})();
