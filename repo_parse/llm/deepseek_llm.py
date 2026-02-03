# ============================================================
# DeepSeek LLM 适配器实现
# ------------------------------------------------------------
# 本模块实现了一个基于 OpenAI SDK 的 LLM 适配器（DeepSeekLLM），
# 用于将仓库内部统一的 LLM 抽象接口（LLM）
# 连接到实际的大模型服务（如 DeepSeek / OpenAI 兼容接口）。
#
# 主要功能：
#   - 从环境变量加载 API 配置
#   - 封装 chat 接口，统一对话格式
#   - 支持流式（stream）响应并实时输出
# ============================================================

from openai import OpenAI
from dotenv import load_dotenv
import os

from repo_parse.llm.llm import LLM

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量中读取模型服务配置
api_base = os.getenv("API_BASE")
api_key = os.getenv("API_KEY")
model_name = os.getenv("MODEL_NAME")


class DeepSeekLLM(LLM):
    """
    DeepSeekLLM 是一个具体的大语言模型客户端实现。

    设计说明：
    - 继承自统一的 LLM 抽象基类
    - 使用 OpenAI SDK 兼容接口进行请求
    - 默认以流式方式获取模型输出
    """

    def __init__(self, api_key=api_key, api_base=api_base, model_name=model_name):
        # 初始化 OpenAI 客户端（兼容 DeepSeek / OpenAI API）
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        # 默认使用的模型名称
        self.model_name = model_name

    def __str__(self) -> str:
        # 模型名称的字符串表示
        return "DeepSeek"

    def chat(self, system_prompt, user_input, model=None, max_tokens=4096, temperature=0, stream=True):
        """
        向大语言模型发起一次对话请求。

        参数说明：
        - system_prompt：系统提示词（角色设定 / 行为约束）
        - user_input：用户输入内容
        - model：可选的模型名称（默认使用初始化时的模型）
        - max_tokens：生成的最大 token 数
        - temperature：采样温度（越低越确定）
        - stream：是否使用流式返回
        """

        # 构造 OpenAI 兼容的消息格式
        history_openai_format = [{"role": "system", "content": system_prompt}]
        history_openai_format.append({"role": "user", "content": user_input})

        # 若未显式指定模型，则使用默认模型
        if model is None:
            model = self.model_name

        # 创建聊天补全请求（支持流式响应）
        response_stream = self.client.chat.completions.create(
            model=model,
            messages=history_openai_format,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

        # 处理并聚合流式输出
        return self._process_stream(response_stream)

    def _process_stream(self, stream):
        """
        处理模型返回的流式响应。

        行为说明：
        - 实时打印模型输出（适合 CLI / 交互式使用）
        - 同时拼接完整响应并返回
        """

        full_response = ""
        for chunk in stream:
            # 从流式增量中提取内容
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            full_response += content
        print("\n")
        return full_response


if __name__ == "__main__":
    # ========================================================
    # 示例用法（本地测试）
    # --------------------------------------------------------
    # 直接运行该文件时，初始化 DeepSeekLLM 并发起一次简单对话
    # ========================================================

    deepseek_llm = DeepSeekLLM()
    response = deepseek_llm.chat(
        system_prompt="You are a helpful assistant",
        user_input="Hello"
    )
    print("Final Response:", response)
