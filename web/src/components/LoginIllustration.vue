<template>
  <div class="illustration">
    <!-- 背景渐变 -->
    <div class="gradient-bg"></div>

    <!-- 主内容 -->
    <div class="content">
      <!-- Logo -->
      <div class="logo-section">
        <svg width="60" height="60" viewBox="0 0 60 60" fill="none">
          <rect x="4" y="24" width="12" height="24" rx="3" fill="white" opacity="0.9"/>
          <rect x="24" y="12" width="12" height="36" rx="3" fill="white" opacity="0.7"/>
          <rect x="44" y="4" width="12" height="44" rx="3" fill="white" opacity="0.5"/>
        </svg>
        <span class="logo-text">Metrics</span>
      </div>

      <!-- AI 机器人图标 -->
      <div class="ai-icon">
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
          <!-- 机器人头部 -->
          <circle cx="60" cy="50" r="35" fill="white" opacity="0.15"/>
          <circle cx="60" cy="50" r="28" fill="white" opacity="0.2"/>
          <!-- 眼睛 -->
          <circle cx="48" cy="45" r="6" fill="white"/>
          <circle cx="72" cy="45" r="6" fill="white"/>
          <!-- 嘴巴/微笑 -->
          <path d="M45 60 Q60 72 75 60" stroke="white" stroke-width="3" fill="none" stroke-linecap="round"/>
          <!-- 天线 -->
          <line x1="60" y1="15" x2="60" y2="5" stroke="white" stroke-width="3" stroke-linecap="round"/>
          <circle cx="60" cy="5" r="4" fill="white"/>
        </svg>
      </div>

      <!-- KPI 卡片 -->
      <div class="kpi-cards">
        <div class="kpi-card">
          <div class="kpi-value">¥12.5M</div>
          <div class="kpi-label">销售额</div>
          <div class="kpi-trend up">↑ 12%</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">3.8%</div>
          <div class="kpi-label">转化率</div>
          <div class="kpi-trend up">↑ 5%</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">8.2K</div>
          <div class="kpi-label">访客数</div>
          <div class="kpi-trend down">↓ 3%</div>
        </div>
      </div>

      <!-- 底部文案 -->
      <div class="bottom-text">
        <h2>智能指标管理平台</h2>
        <p>AI-Driven Data Decisions</p>
      </div>
    </div>

    <!-- 装饰元素 -->
    <div class="decor decor-1"></div>
    <div class="decor decor-2"></div>
    <div class="decor decor-3"></div>
  </div>
</template>

<style scoped>
.illustration {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.gradient-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #00B078 0%, #00A86B 50%, #008B57 100%);
}

.content {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 40px;
}

.logo-text {
  font-size: 28px;
  font-weight: 700;
  color: white;
  letter-spacing: -0.5px;
}

.ai-icon {
  margin-bottom: 40px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.kpi-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 50px;
}

.kpi-card {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 20px 24px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.2);
  min-width: 100px;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  color: white;
  font-family: 'Fira Code', monospace;
}

.kpi-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  margin: 4px 0;
}

.kpi-trend {
  font-size: 12px;
  font-weight: 600;
}

.kpi-trend.up {
  color: #90F0B0;
}

.kpi-trend.down {
  color: #FFB0B0;
}

.bottom-text {
  text-align: center;
  color: white;
}

.bottom-text h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.bottom-text p {
  font-size: 14px;
  opacity: 0.8;
  letter-spacing: 1px;
}

/* 装饰元素 */
.decor {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
}

.decor-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  right: -100px;
}

.decor-2 {
  width: 200px;
  height: 200px;
  bottom: -50px;
  left: -50px;
}

.decor-3 {
  width: 150px;
  height: 150px;
  bottom: 20%;
  right: 10%;
  background: rgba(255, 255, 255, 0.05);
}
</style>
