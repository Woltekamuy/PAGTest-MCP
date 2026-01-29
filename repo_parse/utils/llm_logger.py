"""
This module contains the LLMLogger class, which is used for logging the
raw intput to LLM and the output from LLM, helping us to debug and analyze.
"""
import os
import datetime
import threading

from repo_parse.config import LLM_LOG_DIR

class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()  # 确保线程安全

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

class LLMLogger(metaclass=SingletonMeta):
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _get_log_file_path(self, prefix):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{prefix}_llm_log_{date_str}.log")

    def log_input(self, prefix, user_input):
        log_file_path = self._get_log_file_path(prefix)
        with open(log_file_path, "a") as log_file:
            log_file.write(f"--- User Input ({datetime.datetime.now()}): ---\n")
            log_file.write(user_input + "\n\n")

    def log_response(self, prefix, response):
        log_file_path = self._get_log_file_path(prefix)
        with open(log_file_path, "a") as log_file:
            log_file.write(f"--- LLM Response ({datetime.datetime.now()}): ---\n")
            log_file.write(response + "\n\n")

llm_logger = LLMLogger(log_dir=LLM_LOG_DIR)