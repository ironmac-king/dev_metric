// 直接测试 heading split regex
const text = `#  销售数据分析   ##  数据概览  |  指标 |  数值 |  参考标准  |
| ------|------|---------- |
| 销售额 | ¥754807145.12 | 优秀 |`;

console.log('原始文本:');
console.log(text);
console.log('\n--- 测试不同 regex ---\n');

// 原 regex (不工作的版本)
const regex1 = /^(#{1,6}\s+[^\n]+?)(?=\s+#{1,6}\s)/gm;
const result1 = text.replace(regex1, '$1\n');
console.log('原 regex 结果:');
console.log(result1);

// 新 regex (修复版本)
const regex2 = /^(#{1,6}\s+[^\n]+?)\s{2,}(#{1,6}\s+)/gm;
const result2 = text.replace(regex2, '$1\n$2');
console.log('\n新 regex 结果:');
console.log(result2);

// 更强的 regex - 在行中间也检测 heading
const regex3 = /(?:^|\n)(#{1,6}\s+[^\n]+?)\s{2,}(#{1,6}\s+[^\n]*)/gm;
const result3 = text.replace(regex3, '$1\n$2');
console.log('\n更强 regex 结果:');
console.log(result3);

// 最强版本 - 在任何位置检测 heading
const regex4 = /#{1,6}\s+[^\n#]+(?=\s{2,}#{1,6}\s)/g;
const result4 = text.replace(regex4, (m) => m.replace(/\s{2,}(#{1,6}\s)/, '\n$1'));
console.log('\n最强 regex 结果:');
console.log(result4);
