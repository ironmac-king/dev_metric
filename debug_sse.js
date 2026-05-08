// 调试 SSE 流式输出
async function testStream() {
  const response = await fetch('http://localhost:8081/api/v1/analysis/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: '分析近30天广告投放效果', session_id: '' })
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullContent = ''

  // 解析 SSE
  const parseSSE = (data) => {
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

  let eventType = ''
  let chunkCount = 0

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7)
        continue
      }

      const eventData = parseSSE(line)
      if (!eventData && line.trim() !== 'data:') continue

      if (eventType === 'chunk') {
        chunkCount++
        fullContent += eventData

        // 每100个chunk打印一次内容样例
        if (chunkCount % 100 === 0) {
          console.log(`[Chunk ${chunkCount}] 末尾200字符:`)
          console.log(fullContent.slice(-200))
          console.log('---')
        }
      }
    }
  }

  console.log(`\n=== 总共 ${chunkCount} 个 chunk ===`)
  console.log('最后500字符:')
  console.log(fullContent.slice(-500))

  // 检查换行符
  const newlineCount = (fullContent.match(/\n/g) || []).length
  console.log(`\n换行符数量: ${newlineCount}`)

  // 检查表格行
  const tableRows = fullContent.split('\n').filter(l => l.trim().startsWith('|'))
  console.log(`表格行数量: ${tableRows.length}`)
  if (tableRows.length > 0) {
    console.log('表格行示例:')
    tableRows.slice(0, 5).forEach((row, i) => {
      console.log(`  ${i}: "${row}"`)
    })
  }
}

testStream().catch(console.error)
