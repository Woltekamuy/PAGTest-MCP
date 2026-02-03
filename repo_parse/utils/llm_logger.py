"""
This module contains the LLMLogger class, which is used for logging the
raw intput to LLM and the output from LLM, helping us to debug and analyze.
"""
import os
import datetime
import threading

from repo_parse.config import LLM_LOG_DIR


class SingletonMeta(type):
    """
    线程安全的单例元类（Singleton Metaclass）。

    设计要点：
    - 使用类级别字典 `_instances` 保存已创建的单例实例
    - 使用互斥锁 `_lock` 确保在多线程环境下仅创建一个实例
    - 适用于需要全局唯一实例的资源型对象（如 Logger、Config、Client）
    """
    _instances = {}
    _lock = threading.Lock()  # 确保线程安全

    def __call__(cls, *args, **kwargs):
        """
        重载实例化调用逻辑，实现单例控制。

        在首次调用时创建实例，后续调用直接返回已存在的实例。
        """
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class LLMLogger(metaclass=SingletonMeta):
    """
    LLM 交互日志记录器。

    职责：
    - 以文件形式持久化记录 LLM 的输入（prompt / user input）
    - 记录 LLM 的完整输出结果
    - 按日期自动分割日志文件，避免单文件无限增长

    特性：
    - 通过 SingletonMeta 保证进程内唯一实例
    - 适用于多线程环境（实例创建阶段线程安全）
    """

    def __init__(self, log_dir):
        """
        初始化 LLMLogger。

        :param log_dir: LLM 日志存放目录路径
        """
        self.log_dir = log_dir
        # 若日志目录不存在则自动创建
        os.makedirs(log_dir, exist_ok=True)

    def _get_log_file_path(self, prefix):
        """
        根据前缀与当前日期生成日志文件路径。

        命名规则：
        {prefix}_llm_log_YYYY-MM-DD.log

        :param prefix: 日志前缀（通常为 agent / 模块名称）
        :return: 完整日志文件路径
        """
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{prefix}_llm_log_{date_str}.log")

    def log_input(self, prefix, user_input):
        """
        记录发送给 LLM 的用户输入内容。

        :param prefix: 日志前缀，用于区分不同 agent 或调用源
        :param user_input: 原始用户输入或 prompt 内容
        """
        log_file_path = self._get_log_file_path(prefix)
        with open(log_file_path, "a") as log_file:
            log_file.write(f"--- User Input ({datetime.datetime.now()}): ---\n")
            log_file.write(user_input + "\n\n")

    def log_response(self, prefix, response):
        """
        记录 LLM 返回的响应内容。

        :param prefix: 日志前缀，用于区分不同 agent 或调用源
        :param response: LLM 返回的完整响应文本
        """
        log_file_path = self._get_log_file_path(prefix)
        with open(log_file_path, "a") as log_file:
            log_file.write(f"--- LLM Response ({datetime.datetime.now()}): ---\n")
            log_file.write(response + "\n\n")


# 全局可复用的 LLMLogger 单例实例
# 在整个进程生命周期内共享同一日志器
llm_logger = LLMLogger(log_dir=LLM_LOG_DIR)
