# repo_parse/entrypoint/mcp_server.py
import os
import sys
import json
import logging
import traceback
from typing import List

from mcp.server.fastmcp import FastMCP

# ------------------------------------------------------------
# 内部 API 引用
# ------------------------------------------------------------
# 这些函数实现了核心业务逻辑：
# - parse                : Java 源码解析（AST 级）
# - build_metainfo       : 类 / 方法 / 测试元信息构建
# - analyze_testcases    : 基于 LLM 的测试用例分析
# - genereate_testcases  : 基于 LLM 的测试生成
# - load_dotenv_file     : LLM / 环境配置加载与校验
# 你已有的 API
from repo_parse.entrypoint.api import (
    parse, build_metainfo, analyze_testcases, genereate_testcases, load_dotenv_file
)

# ------------------------------------------------------------
# MCP 服务实例
# ------------------------------------------------------------
# 说明：
# - host / port 通过构造器注入，便于容器化与多环境部署
# - run() 时只需指定 transport="sse"
# 通过构造器设置 host/port；run() 只传 transport="sse"
mcp = FastMCP(
    "mcp-java-testgen",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "3923")),
)

# ------------------------------------------------------------
# 仓库路径校验
# ------------------------------------------------------------
# 安全与一致性保障：
# - 必须为绝对路径（避免服务端访问意外目录）
# - 必须为真实存在的目录
def _validate_repo_path(repo_path: str):
    if not os.path.isabs(repo_path):
        raise ValueError("repo_path must be an absolute path.")
    if not os.path.isdir(repo_path):
        raise ValueError(f"Invalid repo_path: {repo_path}")

# ------------------------------------------------------------
# 成功返回统一封装
# ------------------------------------------------------------
# MCP Tool 约定返回 string，这里统一 JSON 序列化
def _ok(payload: dict) -> str:
    payload.setdefault("success", True)
    return json.dumps(payload, ensure_ascii=False)

# ------------------------------------------------------------
# 错误返回统一封装
# ------------------------------------------------------------
# 设计要点：
# - success=false 明确失败语义
# - error_type    便于客户端区分异常类型
# - traceback     便于调试（客户端可选择忽略）
def _err(e: Exception) -> str:
    return json.dumps({
        "success": False,
        "error_type": type(e).__name__,
        "error": str(e),
        "traceback": traceback.format_exc(),
    }, ensure_ascii=False)

# ============================================================
# MCP Tool: parse_repo
# ============================================================
# 功能：
# - 解析 Java 仓库源码
# - 生成 AST 级中间数据
# - 创建 .PAGTest/ 工作目录
@mcp.tool("parse_repo")
async def parse_repo(repo_path: str) -> str:
    """Parse Java source code into AST metadata. Creates .PAGTest/ directory."""
    try:
        _validate_repo_path(repo_path)
        parse(repo_path=repo_path, language="Java")
        return _ok({
            "message": f"Repository parsed. Metadata saved to {repo_path}/.PAGTest/"
        })
    except Exception as e:
        return _err(e)

# ============================================================
# MCP Tool: build_metainfo
# ============================================================
# 功能：
# - 在 AST 结果之上构建结构化元信息
# - 包含类、方法、已有测试用例等
@mcp.tool("build_metainfo")
async def build_meta(repo_path: str) -> str:
    """Build structured class/method/test metadata from parsed AST."""
    try:
        _validate_repo_path(repo_path)
        build_metainfo(repo_path=repo_path)
        return _ok({"message": "Metainfo built successfully."})
    except Exception as e:
        return _err(e)

# ============================================================
# MCP Tool: analyze_testcases
# ============================================================
# 功能：
# - 使用 LLM 分析已有测试用例
# - 构建测试知识库（KB）
# - 支持批量模式与过滤列表
@mcp.tool("analyze_testcases")
async def analyze(
    repo_path: str,
    is_batch: bool=False,
    filter_list: List[str] | None=None
) -> str:
    """Analyze existing test cases using LLM to build KB."""
    try:
        _validate_repo_path(repo_path)

        # 校验 LLM / 环境变量配置
        ok, msg = load_dotenv_file()
        if not ok:
            raise RuntimeError(f"LLM configuration error: {msg}")

        status, error = analyze_testcases(
            repo_path=repo_path,
            is_batch=is_batch,
            filter_list=filter_list or []
        )
        if status != "success":
            raise RuntimeError(f"Analysis failed: {error}")

        return _ok({
            "message": "Testcase analysis completed. Knowledge base built in .PAGTest/.",
            "output_files": [
                ".PAGTest/testcase_analysis_result.json",
                ".PAGTest/method_to_primary_testcase.json",
                ".PAGTest/node_coordinator_result.json"
            ]
        })
    except Exception as e:
        return _err(e)

# ============================================================
# MCP Tool: generate_testcase
# ============================================================
# 功能：
# - 针对指定类 + 方法生成单元测试
# - 内部由 LLM 驱动
# - 返回生成的测试类名与结果路径
@mcp.tool("generate_testcase")
async def generate(repo_path: str, target_class: str, target_method: str) -> str:
    """Generate a unit test for a specific Java method."""
    try:
        _validate_repo_path(repo_path)

        # 校验 LLM / 环境变量配置
        ok, msg = load_dotenv_file()
        if not ok:
            raise RuntimeError(f"LLM configuration error: {msg}")

        # 基础参数校验
        if not target_class or not target_method:
            raise ValueError("Missing target_class or target_method")

        uri, class_name, results, error = genereate_testcases(
            repo_path=repo_path,
            target_method=target_method,
            target_class=target_class
        )
        if error:
            raise RuntimeError(f"Test generation failed: {error}")

        return _ok({
            "target_method_uri": uri,
            "generated_test_class": class_name,
            "generated_testcases": results
        })
    except Exception as e:
        return _err(e)

# ============================================================
# 服务启动入口
# ============================================================
def main():
    # --------------------------------------------------------
    # 日志配置
    # --------------------------------------------------------
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO")
    )
    logging.info("Starting MCP SSE server")

    # --------------------------------------------------------
    # 启动 MCP 服务
    # --------------------------------------------------------
    # 注意：
    # - host / port 已在 FastMCP 构造器中设置
    # - SSE 路径默认为 /sse
    # 这里 run 只传 transport；host/port 由构造器注入，SSE 路径默认为 /sse
    mcp.run(transport="sse")

if __name__ == "__main__":
    main()
