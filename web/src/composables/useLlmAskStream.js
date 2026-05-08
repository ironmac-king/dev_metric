export async function runLlmAskStream({
  question,
  sessionId,
  token,
  userId,
  signal,
  onEvent,
}) {
  const response = await fetch('/api/v1/llm-ask/v2/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
    signal,
    body: JSON.stringify({
      question,
      user_id: userId || 'default',
      session_id: sessionId || undefined,
    }),
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
        continue
      }

      if (!line.startsWith('data: ')) {
        continue
      }

      const dataStr = line.slice(6).trim()
      if (!dataStr) {
        currentEvent = ''
        continue
      }

      try {
        const data = JSON.parse(dataStr)
        if (onEvent) {
          onEvent(currentEvent, data)
        }
      } catch {
        // Ignore malformed SSE payloads and continue consuming the stream.
      }

      currentEvent = ''
    }
  }
}
