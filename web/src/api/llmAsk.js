/**
 * LLM.V1 & V2 API 封装
 */
import request from './index'

export const llmAskApi = {
  /**
   * 发送问题 (V1)
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
   * 发送问题 (V2)
   * @param {Object} params - { question, session_id }
   */
  askV2(params) {
    return request({
      url: '/llm-ask/v2',
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

/**
 * 会话管理 API
 */
export const sessionApi = {
  /**
   * 获取会话列表
   */
  list() {
    return request({
      url: '/ask/sessions',
      method: 'get',
    })
  },

  /**
   * 保存会话摘要（创建或更新）
   * @param {Object} data - { session_id, title, first_question }
   */
  save(data) {
    return request({
      url: '/ask/sessions',
      method: 'post',
      data,
    })
  },

  /**
   * 删除会话
   * @param {string} sessionId - 会话ID
   */
  delete(sessionId) {
    return request({
      url: `/ask/sessions/${sessionId}`,
      method: 'delete',
    })
  },
}
