# client_java_testgen_sse.py
import asyncio
import json
import os
import time
from typing import Optional, List, Any, Tuple

from mcp import ClientSession
from mcp.client.sse import sse_client


# ------------------------------------------------------------
# 确保 MCP 服务地址以 /sse 结尾
# ------------------------------------------------------------
# 统一 SSE 入口，避免调用方传入不规范 URL
def _ensure_sse_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    return url if url.endswith("/sse") else (url + "/sse")


# ------------------------------------------------------------
# MCP 服务端地址
# ------------------------------------------------------------
# 优先从环境变量 MCP_URL 获取，便于多环境部署
MCP_URL = _ensure_sse_url(os.environ.get("MCP_URL", "http://127.0.0.1:3923"))


# ------------------------------------------------------------
# 统一的异步 → 同步执行适配器
# ------------------------------------------------------------
# 设计目标：
# - 兼容普通 Python 脚本
# - 兼容 Jupyter / IPython 等已存在事件循环的环境
def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    # 在已有事件循环中运行（如 Notebook）
    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)


# ------------------------------------------------------------
# 打开 MCP SSE 会话
# ------------------------------------------------------------
# 返回：
# - sse_ctx     : SSE 上下文管理器
# - streams     : SSE 数据流
# - sess        : MCP ClientSession 实例
# - sess_ctx    : ClientSession 上下文管理器
async def _open_session() -> Tuple[Any, Any, ClientSession, Any]:
    sse_ctx = sse_client(url=MCP_URL)
    streams = await sse_ctx.__aenter__()
    sess_ctx = ClientSession(*streams)
    sess = await sess_ctx.__aenter__()
    return sse_ctx, streams, sess, sess_ctx


# ------------------------------------------------------------
# 关闭 MCP SSE 会话
# ------------------------------------------------------------
# 确保连接、流、上下文被正确释放，避免资源泄漏
async def _close_session(sse_ctx, sess_ctx):
    await sess_ctx.__aexit__(None, None, None)
    await sse_ctx.__aexit__(None, None, None)


# ------------------------------------------------------------
# 核心异步调用封装
# ------------------------------------------------------------
# 功能：
# - 建立 SSE 连接
# - 初始化 MCP 会话
# - 调用指定工具
# - 统一解析 JSON / 错误返回
async def _async_call(tool: str, params: dict) -> dict:
    sse_ctx, streams, session, sess_ctx = await _open_session()
    try:
        await session.initialize()
        result = await session.call_tool(tool, params)

        # ----------------------------------------------------
        # 错误兜底：SDK 可能将错误包装为纯文本
        # ----------------------------------------------------
        if getattr(result, "is_error", False):
            text = (result.content[0].text if result.content else "") or ""
            try:
                return json.loads(text)
            except Exception:
                return {
                    "success": False,
                    "server_error": True,
                    "raw_text": text
                }

        # ----------------------------------------------------
        # 正常返回路径：尝试解析 JSON
        # ----------------------------------------------------
        if result.content and hasattr(result.content[0], "text"):
            text = result.content[0].text or ""
            try:
                return json.loads(text)
            except Exception:
                return {
                    "success": False,
                    "raw_text": text,
                    "error": "非 JSON 文本返回"
                }

        return {"success": False, "error": "没有返回内容"}

    finally:
        await _close_session(sse_ctx, sess_ctx)


# ------------------------------------------------------------
# 带重试的同步调用封装
# ------------------------------------------------------------
# 设计目的：
# - 提升网络/服务抖动下的稳定性
# - 对外暴露简单、健壮的同步 API
def _call_with_retry(
    tool: str,
    params: dict,
    retries: int = 3,
    delay: float = 0.5
) -> dict:
    last = None
    for i in range(retries):
        try:
            return _run(_async_call(tool, params))
        except Exception as e:
            last = e
            if i < retries - 1:
                print(f"[{tool}] attempt {i+1} failed: {e} -> retrying...")
                time.sleep(delay)
    return {"success": False, "error": f"调用失败: {last}"}


# ============================================================
# 业务封装：与 MCP 服务端工具一一对应
# ============================================================

# ------------------------------------------------------------
# 解析 Java 仓库（构建 AST / 初始结构）
# ------------------------------------------------------------
def parse_repo(repo_path: str) -> dict:
    return _call_with_retry("parse_repo", {"repo_path": repo_path})


# ------------------------------------------------------------
# 构建方法 / 类级元信息
# ------------------------------------------------------------
def build_metainfo(repo_path: str) -> dict:
    return _call_with_retry("build_metainfo", {"repo_path": repo_path})


# ------------------------------------------------------------
# 分析已有测试用例（支持批量 / 过滤）
# ------------------------------------------------------------
def analyze_testcases(
    repo_path: str,
    is_batch: bool = False,
    filter_list: Optional[List[str]] = None
) -> dict:
    return _call_with_retry("analyze_testcases", {
        "repo_path": repo_path,
        "is_batch": bool(is_batch),
        "filter_list": filter_list or []
    })


# ------------------------------------------------------------
# 为指定类 + 方法生成测试用例
# ------------------------------------------------------------
def generate_testcase(repo_path: str, target_class: str, target_method: str) -> dict:
    return _call_with_retry("generate_testcase", {
        "repo_path": repo_path,
        "target_class": target_class,
        "target_method": target_method
    })


# ============================================================
# 示例 CLI（本地调试 / 手动验证用）
# ============================================================
if __name__ == "__main__":
    # --------------------------------------------------------
    # 要求使用绝对路径（服务端会进行校验）
    # --------------------------------------------------------
    REPO_PATH = os.environ.get(
        "REPO_PATH",
        "/home/zhangzhe/PAGTest/workspace/commons-collections"
    )
    print(REPO_PATH)

    # Step 1: 解析仓库
    r1 = parse_repo(REPO_PATH)
    print("parse_repo =>", r1)

    # Step 2: 构建元信息
    r2 = build_metainfo(REPO_PATH)
    print("build_metainfo =>", r2)

    # Step 3: 分析测试用例
    r3 = analyze_testcases(REPO_PATH, is_batch=True)
    print("analyze_testcases =>", r3)

    # Step 4: 生成指定方法的测试用例
    r4 = generate_testcase(REPO_PATH, "SimpleQueue", "[void]enqueue(T)")
    print("generate_testcase =>", r4)
