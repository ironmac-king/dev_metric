const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // 记录 DOM 更新的时间点
  const updates = [];
  let lastContent = '';

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('流式完成')) {
      console.log('[EVENT] 流式完成');
    }
  });

  // 监控 result-text 的内容变化
  await page.goto('http://localhost:3001/analysis', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);

  // 注入监控代码
  await page.evaluate(() => {
    const observer = new MutationObserver((mutations) => {
      const resultText = document.querySelector('.result-text');
      if (resultText) {
        const content = resultText.innerHTML;
        console.log('[DOM UPDATE] content length:', content.length, 'first 50:', content.substring(0, 50));
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  });

  // 输入查询
  const input = page.locator('textarea').first();
  await input.fill('分析近30天广告');
  await input.press('Enter');

  // 等待一段时间观察
  await page.waitForTimeout(30000);

  // 获取最终结果
  const finalContent = await page.locator('.result-text').innerHTML().catch(() => 'N/A');
  console.log('\n=== FINAL RESULT (first 500 chars) ===');
  console.log(finalContent.substring(0, 500));

  await browser.close();
})();
