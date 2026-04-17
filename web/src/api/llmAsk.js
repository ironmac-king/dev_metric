/**
 * LLM.V1 API 封装
 */
import request from './index'

export const llmAskApi = {
  /**
   * 发送问题
   * @param {Object} params - { question, session_id }
   */
  ask(params) {
    return request({
      url: '/llm-ask',
      method: 'post',
      data: params,
    })
  },

  /**
   * 获取会话历史
   * @param {string} sessionId - 会话ID
   */
  getHistory(sessionId) {
    return request({
      url: `/llm-ask/history/${sessionId}`,
      method: 'get',
    })
  },

  /**
   * 清除会话
   * @param {string} sessionId - 会话ID
   */
  clearSession(sessionId) {
    return request({
      url: '/llm-ask/clear',
      method: 'post',
      params: { session_id: sessionId },
    })
  },
}
