"""
本模块提供一个用于记录 LLM（大语言模型）交互过程的装饰器工厂。

核心用途：
- 在方法调用前自动捕获 system_prompt 与 user_input
- 将用户输入与模型输出统一记录到 llm_logger
- 通过 wraps 保留被装饰函数的元数据（如函数名、docstring）

典型应用场景：
- Agent / Tool / Service 层中对 LLM 调用的审计与调试
- 统一的 Prompt / Response 日志收集
"""

from functools import wraps

from repo_parse.utils.llm_logger import llm_logger


def log_llm_interaction(agent_name):
    """
    装饰器工厂，用于为指定 agent 注入 LLM 交互日志能力。

    :param agent_name: Agent 或模块名称，用于日志分类与标识
    :return: 装饰器
    """

    def decorator(func):
        """
        实际装饰器，用于包裹目标函数。

        :param func: 被装饰的实例方法（通常为 Agent 的成员方法）
        :return: 包装后的函数
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            包装函数，在原函数执行前后插入日志逻辑。

            约定：
            - system_prompt 与 user_input 通过 kwargs 传入
            - 被装饰函数返回值视为 LLM 的完整响应
            """
            # 从关键字参数中提取 system prompt 与用户输入
            system_prompt = kwargs.get('system_prompt')
            user_input = kwargs.get('user_input')
            # 控制台输出当前交互内容，便于本地调试
            print("System Prompt:", system_prompt, "\nUser Input:", user_input, "\n")

            # 若 system_prompt 与 user_input 均存在，则记录用户输入
            if system_prompt and user_input:
                llm_logger.log_input(agent_name, user_input)

            # 执行被装饰的原始函数，获取完整响应
            full_response = func(self, *args, **kwargs)

            # 若函数返回了响应内容，则记录 LLM 输出
            if full_response:
                llm_logger.log_response(agent_name, full_response)
            # 返回原函数的执行结果，不做任何修改
            return full_response

        return wrapper

    return decorator
