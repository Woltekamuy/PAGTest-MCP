# client_java_testgen_sse.py
import asyncio
import json
import os
import time
from typing import Optional, List, Any, Tuple

from mcp import ClientSession
from mcp.client.sse import sse_client

def _ensure_sse_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    return url if url.endswith("/sse") else (url + "/sse")

MCP_URL = _ensure_sse_url(os.environ.get("MCP_URL", "http://127.0.0.1:3923"))

def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)

async def _open_session() -> Tuple[Any, Any, ClientSession, Any]:
    sse_ctx = sse_client(url=MCP_URL)
    streams = await sse_ctx.__aenter__()
    sess_ctx = ClientSession(*streams)
    sess = await sess_ctx.__aenter__()
    return sse_ctx, streams, sess, sess_ctx

async def _close_session(sse_ctx, sess_ctx):
    await sess_ctx.__aexit__(None, None, None)
    await sse_ctx.__aexit__(None, None, None)

async def _async_call(tool: str, params: dict) -> dict:
    sse_ctx, streams, session, sess_ctx = await _open_session()
    try:
        await session.initialize()
        result = await session.call_tool(tool, params)

        # 若 SDK 把错误作为纯文本返回，服务端也已 JSON 包装；这里仍保底
        if getattr(result, "is_error", False):
            text = (result.content[0].text if result.content else "") or ""
            try:
                return json.loads(text)
            except Exception:
                return {"success": False, "server_error": True, "raw_text": text}

        if result.content and hasattr(result.content[0], "text"):
            text = result.content[0].text or ""
            try:
                return json.loads(text)
            except Exception:
                return {"success": False, "raw_text": text, "error": "非 JSON 文本返回"}

        return {"success": False, "error": "没有返回内容"}

    finally:
        await _close_session(sse_ctx, sess_ctx)

def _call_with_retry(tool: str, params: dict, retries: int = 3, delay: float = 0.5) -> dict:
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

# --------- 业务封装：和服务器的 4 个工具一一对应 ---------

def parse_repo(repo_path: str) -> dict:
    return _call_with_retry("parse_repo", {"repo_path": repo_path})

def build_metainfo(repo_path: str) -> dict:
    return _call_with_retry("build_metainfo", {"repo_path": repo_path})

def analyze_testcases(repo_path: str, is_batch: bool=False, filter_list: Optional[List[str]]=None) -> dict:
    return _call_with_retry("analyze_testcases", {
        "repo_path": repo_path,
        "is_batch": bool(is_batch),
        "filter_list": filter_list or []
    })

def generate_testcase(repo_path: str, target_class: str, target_method: str) -> dict:
    return _call_with_retry("generate_testcase", {
        "repo_path": repo_path,
        "target_class": target_class,
        "target_method": target_method
    })

# -------------- 示例 CLI -----------------
if __name__ == "__main__":
    # 要求绝对路径（服务端会校验）
    REPO_PATH = os.environ.get("REPO_PATH", "/home/zhangzhe/PAGTest/workspace/commons-collections")
    print(REPO_PATH)
    r1 = parse_repo(REPO_PATH)
    print("parse_repo =>", r1)

    r2 = build_metainfo(REPO_PATH)
    print("build_metainfo =>", r2)

    r3 = analyze_testcases(REPO_PATH, is_batch=True)
    print("analyze_testcases =>", r3)

    r4 = generate_testcase(REPO_PATH, "ArrayStack", "[int]search(Object)")
    print("generate_testcase =>", r4)
