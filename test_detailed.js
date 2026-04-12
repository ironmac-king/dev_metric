// 详细测试 formatResult 的各个步骤
const testText = `#  销售数据分析   ##  数据概览  |  指标 |  数值 |  参考标准  |
| ------|------|---------- |
| 销售额 | ¥754807145.12 | 优秀 |`;

function formatResult(text) {
  if (!text) return '';

  console.log('[formatResult] 原始文本:', text.substring(0, 100));

  // 0. 移除图表数据标记
  text = text.replace(/\{ ?CHART_DATA ?:\s*\{[\s\S]*?\} ?\}/gi, '');
  text = text.replace(/\[\[CHART_BLOCK\]\]/g, '');

  // 1a. 修复加粗标记周围的空格
  text = text.replace(/\*\*\s+(.+?)\s+\*\*/g, '**$1**');
  // 1b. 处理加粗标签
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // 1c. 修复被断开的 markdown 标题
  console.log('[formatResult] 1c 执行前:', text.substring(0, 80));
  text = text.replace(/^(#{1,6}\s+[^\n]+?)\s{2,}(#{1,6}\s+)/gm, '$1\n$2');
  console.log('[formatResult] 1c 执行后:', text.substring(0, 100));

  // 1e. 修复 heading 和 table 在同一行
  text = text.replace(/^(#{1,6}\s+[^\n]+?)\s+\|/gm, '$1\n|');

  // 1d. 修复标题后的表格行
  text = text.replace(/^(#{1,6}\s+.+?)(\s+)(\|)/gm, '$1\n$3');

  // 2. 规范化行结束符
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // 3. 分割内容为行
  const lines = text.split('\n');
  console.log('[formatResult] 总行数:', lines.length);
  console.log('[formatResult] 前5行:', lines.slice(0, 5));

  return text; // 简化版，直接返回处理后的文本
}

const result = formatResult(testText);
console.log('\n=== 最终结果 ===');
console.log(result.substring(0, 200));
