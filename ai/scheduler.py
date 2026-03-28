"""
定时调度器 - 每日分析负反馈生成优化建议
"""
from threading import Thread
import time
from datetime import datetime, timedelta
import os


class DailyScheduler:
    """每日定时调度器"""

    def __init__(self):
        self._running = False
        self._thread = None
        # 调度时间：每天凌晨2点
        self._hour = 2
        self._minute = 0

    def _get_next_run_time(self) -> datetime:
        """计算下次执行时间"""
        now = datetime.now()
        next_run = now.replace(hour=self._hour, minute=self._minute, second=0, microsecond=0)

        # 如果今天已经过了执行时间，则安排明天
        if now >= next_run:
            next_run += timedelta(days=1)

        return next_run

    def _sleep_until_next_run(self):
        """睡眠到下次执行时间"""
        next_run = self._get_next_run_time()
        now = datetime.now()
        seconds_until_run = (next_run - now).total_seconds()

        print(f"[Scheduler] 下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[Scheduler] 距离执行还有 {seconds_until_run:.0f} 秒")

        # 先睡眠到接近执行时间
        if seconds_until_run > 60:
            time.sleep(seconds_until_run - 60)

        # 然后精确等待
        while True:
            now = datetime.now()
            if now.hour == self._hour and now.minute >= self._minute:
                break
            time.sleep(30)

    def _run_daily_analysis(self):
        """执行每日分析"""
        try:
            from ai.feedback.rule_optimizer import get_rule_optimizer
            optimizer = get_rule_optimizer()
            suggestions = optimizer.daily_analysis()
            print(f"[Scheduler] 每日分析完成，发现 {len(suggestions)} 条优化建议")
        except Exception as e:
            print(f"[Scheduler] 每日分析执行失败: {e}")

    def _scheduler_loop(self):
        """调度循环"""
        print(f"[Scheduler] 定时调度器已启动，每天 {self._hour}:{self._minute:02d} 执行")

        while self._running:
            try:
                # 睡眠到下次执行时间
                self._sleep_until_next_run()

                # 执行每日分析
                if self._running:
                    print(f"[Scheduler] 开始执行每日分析 at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    self._run_daily_analysis()

                    # 执行完后睡眠一段时间，避免重复执行
                    time.sleep(120)  # 等待2分钟

            except Exception as e:
                print(f"[Scheduler] 调度循环出错: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续

    def start(self):
        """启动调度器"""
        if self._running:
            print("[Scheduler] 调度器已在运行中")
            return

        self._running = True
        self._thread = Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        print("[Scheduler] 调度器已启动")

    def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] 调度器已停止")

    def run_now(self):
        """立即执行一次分析（用于测试）"""
        print("[Scheduler] 立即执行每日分析...")
        self._run_daily_analysis()


# 全局单例
_daily_scheduler = None


def start_daily_scheduler() -> DailyScheduler:
    """启动每日调度器"""
    global _daily_scheduler
    if _daily_scheduler is None:
        _daily_scheduler = DailyScheduler()
    _daily_scheduler.start()
    return _daily_scheduler


def get_daily_scheduler() -> DailyScheduler:
    """获取调度器实例"""
    global _daily_scheduler
    return _daily_scheduler
