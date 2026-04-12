// 精确测试 parseSSE 函数

// 原始版本
const parseSSE_original = (data) => {
  const lines = data.split('\n')
  const dataLines = []
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      dataLines.push(line.slice(6))
    } else if (line === 'data:') {
      dataLines.push('')
    }
  }
  return dataLines.join('\n')
}

// 修复版本
const parseSSE_fixed = (data) => {
  const lines = data.split('\n')
  const dataLines = []
  for (const line of lines) {
    if (!line) continue

    if (line.startsWith('data: ')) {
      dataLines.push(line.slice(6))
    }
    else if (line.startsWith('data:')) {
      const afterData = line.slice(5)
      if (afterData === '' || afterData === ' ') {
        dataLines.push('')
      } else {
        dataLines.push(afterData)
      }
    }
  }
  return dataLines.join('\n')
}

// 测试数据 - 模拟后端发送的原始 SSE chunk
const testChunks = [
  "event: chunk\ndata: |",
  "data:  指标 |",
  "data:  数值 |",
  "data:  参考标准",
  "data:  |",
  "data: |------",
  "data: |------|",
  "data: ----------|",
  "data: |",
  "data:  销售额 |",
  "data:  ¥763,",
  "data: 449,655",
  "data: .61",
  "data:  | 优秀",
  "data: =高,",
  "data:  良好=",
  "data: 中 |",
  "data: ",
  "data: ",
  "data: ## 销售",
  "data: 趋势分析",
];

console.log("=== 模拟 parseSSE 处理 ===\n");

let fullContent_fixed = "";
let fullContent_original = "";

for (const chunk of testChunks) {
  console.log("输入:", JSON.stringify(chunk));

  const result_fixed = parseSSE_fixed(chunk);
  const result_original = parseSSE_original(chunk);

  console.log("修复版输出:", JSON.stringify(result_fixed));
  console.log("原始版输出:", JSON.stringify(result_original));

  fullContent_fixed += result_fixed;
  fullContent_original += result_original;

  console.log("---");
}

console.log("\n=== 最终拼接结果 ===");
console.log("修复版换行符数量:", (fullContent_fixed.match(/\n/g) || []).length);
console.log("原始版换行符数量:", (fullContent_original.match(/\n/g) || []).length);
console.log("\n修复版末尾200字符:");
console.log(fullContent_fixed.slice(-200));
console.log("\n原始版末尾200字符:");
console.log(fullContent_original.slice(-200));
