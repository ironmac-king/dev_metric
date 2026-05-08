// 测试修复后的 parseSSE 函数

// 修复版本
const parseSSE = (data) => {
  const lines = data.split('\n')
  const dataLines = []
  for (const line of lines) {
    if (!line) continue // 跳过空行

    // 优先匹配 "data: xxx" 格式（有空格）
    if (line.startsWith('data: ')) {
      const content = line.slice(6)
      // 如果是空内容（data: 后面只有空格），表示换行
      if (content.trim() === '') {
        dataLines.push('\n')
      } else {
        dataLines.push(content)
      }
    }
    // 处理 "data:xxx" 或 "data:" 格式（无空格或空内容）
    else if (line.startsWith('data:')) {
      const afterData = line.slice(5)
      if (afterData.trim() === '') {
        // 空 data: 行表示换行
        dataLines.push('\n')
      } else {
        // data:xxx 格式（无空格）
        dataLines.push(afterData)
      }
    }
  }
  return dataLines.join('')
}

// 模拟完整的 SSE chunk 数据（模拟后端每次 send 发送的内容）
// 这是真实的 SSE 格式：每个 event: chunk 后面跟着多个 data: 行
const sseChunks = [
  // 第一个 chunk：event 行 + 一个 data 行
  "event: chunk\ndata: |",
  // 第二个 chunk：多个 data 行（表头片段）
  "data:  指标 |\ndata:  数值 |\ndata:  参考标准",
  // 第三个 chunk：空行
  "data: ",
  // 第四个 chunk：分隔线
  "data: |------",
  // 第五个 chunk：更多分隔线
  "data: |------|\ndata: ----------|",
  // 第六个 chunk：空行
  "data: ",
  // 第七个 chunk：销售额行开始
  "data: |",
  "data:  销售额 |",
  "data:  ¥763,",
  "data:  449,655",
  "data: .61",
  "data:  | 优秀",
  // 第八个 chunk：空行
  "data: ",
  // 第九个 chunk：第二个指标
  "data:  页面访问\ndata: 量|",
  // 第十个 chunk：空行
  "data: \ndata: ",
  // 第十一个 chunk：标题
  "data: ## 销售\ndata: 趋势分析",
];

console.log("=== 测试修复后的 parseSSE ===\n");

let fullContent = "";

for (const chunk of sseChunks) {
  console.log("输入:", JSON.stringify(chunk));
  const result = parseSSE(chunk);
  console.log("输出:", JSON.stringify(result));
  fullContent += result;
  console.log("---");
}

console.log("\n=== 最终拼接结果 ===");
console.log("换行符数量:", (fullContent.match(/\n/g) || []).length);
console.log("\n完整拼接结果:");
console.log(fullContent);
