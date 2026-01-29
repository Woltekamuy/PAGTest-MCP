# repo_parse/entrypoint/mcp_server.py
import os
import sys
import json
import logging
import traceback
from typing import List

from mcp.server.fastmcp import FastMCP

# 你已有的 API
from repo_parse.entrypoint.api import (
    parse, build_metainfo, analyze_testcases, genereate_testcases, load_dotenv_file
)

# 通过构造器设置 host/port；run() 只传 transport="sse"
mcp = FastMCP(
    "mcp-java-testgen",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "3923")),
)

def _validate_repo_path(repo_path: str):
    if not os.path.isabs(repo_path):
        raise ValueError("repo_path must be an absolute path.")
    if not os.path.isdir(repo_path):
        raise ValueError(f"Invalid repo_path: {repo_path}")

def _ok(payload: dict) -> str:
    payload.setdefault("success", True)
    return json.dumps(payload, ensure_ascii=False)

def _err(e: Exception) -> str:
    return json.dumps({
        "success": False,
        "error_type": type(e).__name__,
        "error": str(e),
        "traceback": traceback.format_exc(),
    }, ensure_ascii=False)

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

@mcp.tool("build_metainfo")
async def build_meta(repo_path: str) -> str:
    """Build structured class/method/test metadata from parsed AST."""
    try:
        _validate_repo_path(repo_path)
        build_metainfo(repo_path=repo_path)
        return _ok({"message": "Metainfo built successfully."})
    except Exception as e:
        return _err(e)

@mcp.tool("analyze_testcases")
async def analyze(repo_path: str, is_batch: bool=False, filter_list: List[str] | None=None) -> str:
    """Analyze existing test cases using LLM to build KB."""
    try:
        _validate_repo_path(repo_path)
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

@mcp.tool("generate_testcase")
async def generate(repo_path: str, target_class: str, target_method: str) -> str:
    """Generate a unit test for a specific Java method."""
    try:
        _validate_repo_path(repo_path)
        ok, msg = load_dotenv_file()
        if not ok:
            raise RuntimeError(f"LLM configuration error: {msg}")
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

def main():
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"))
    logging.info("Starting MCP SSE server")
    # 这里 run 只传 transport；host/port 由构造器注入，SSE 路径默认为 /sse
    mcp.run(transport="sse")

if __name__ == "__main__":
    main()
