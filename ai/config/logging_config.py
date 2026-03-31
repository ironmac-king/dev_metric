"""
Python AI 服务日志配置
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """
    初始化 Python AI 服务的日志配置

    Args:
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_dir: 日志文件目录
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有的 handlers
    root_logger.handlers.clear()

    # JSON formatter
    json_formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={
            "asctime": "time",
            "levelname": "level",
            "name": "service",
            "message": "msg",
        }
    )

    # 文件 handler - 按大小轮转
    log_file = os.path.join(log_dir, f"ai-{os.environ.get('HOSTNAME', 'local')}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=0,  # 保留全部，不自动删除
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 控制台 handler - 同样输出 JSON
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称，如果为 None 则返回根日志器

    Returns:
        日志器实例
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger()
