# ============================================================
# ScopeGraph 构建器（基于 Tree-sitter）
# ------------------------------------------------------------
# 本模块负责：
#   - 使用 tree-sitter 对源代码进行语法解析
#   - 通过 query 捕获作用域、定义、引用、导入等语义节点
#   - 将捕获结果转换为 ScopeGraph（作用域关系图）
#
# ============================================================

import traceback
from typing import Dict, List, Tuple
from tree_sitter_languages import get_language, get_parser

from repo_parse.scope_graph.scope_resolution import LocalScope, LocalDef, Reference, Scoping
from repo_parse.scope_graph.scope_resolution.imports import (
    LocalImportStmt,
    parse_from,
    parse_alias,
    parse_name,
)
from repo_parse.scope_graph.utils import TextRange
from repo_parse.scope_graph.scope_resolution.graph import ScopeGraph

from repo_parse.scope_graph.ts.capture_types import (
    LocalDefCapture,
    LocalRefCapture,
    LocalImportPartCapture,
    ImportPartType,
)

from repo_parse.config import JAVA_SCM

# 不同语言中，哪些语法节点可被视为“命名空间相关符号”
NAMESPACES = {
    "python": ["class", "function", "parameter", "variable"],
    "java": ["class", "method", "parameter", "variable"]
}


def get_language_query_file(language: str) -> str:
    # 根据语言返回对应的 tree-sitter 查询文件路径
    if language == "java":
        return JAVA_SCM
    else:
        raise ValueError(f"Unsupported language: {language}")


def build_query(file_content: bytearray, language: str) -> Tuple:
    """
    构建 tree-sitter 查询对象与语法树根节点。

    返回：
    - query：tree-sitter Query 对象
    - root：解析后的语法树根节点
    """
    try:
        # 获取 tree-sitter 语言与解析器
        language_sitter = get_language(language)
        parser = get_parser(language)
        # 加载语言对应的 query 文件
        query_file_path = get_language_query_file(language)
        query_file_content = open(query_file_path, "rb").read()

        # 解析源代码并生成语法树
        root = parser.parse(file_content).root_node
        query = language_sitter.query(query_file_content)
        return query, root
    except Exception as e:
        # 捕获并包装异常，附带完整调用栈
        raise RuntimeError(f"Failed to build query for language {language}: {e}, trace: {traceback.format_exc()}")


def build_scope_graph(src_bytes: bytearray, language: str = "python") -> ScopeGraph:
    """
    从源代码字节流构建 ScopeGraph。

    构建流程概览：
    1. 使用 tree-sitter 执行 query 捕获语义节点
    2. 分类收集作用域、定义、引用、导入相关捕获
    3. 按顺序向 ScopeGraph 中插入节点与关系
    """

    # 构建 query 与语法树
    query, root_node = build_query(src_bytes, language)

    # 各类捕获结果的暂存容器
    local_def_captures: List[LocalDefCapture] = []
    local_ref_captures: List[LocalRefCapture] = []
    local_scope_capture_indices: List[int] = []
    local_import_stmt_capture_indices: List[int] = []
    local_import_part_captures: List[LocalImportPartCapture] = []

    # capture index -> TextRange 的映射
    capture_map: Dict[int, TextRange] = {}

    # 遍历所有 query 捕获
    for i, (node, capture_name) in enumerate(query.captures(root_node)):
        # 将 tree-sitter 节点位置转换为 TextRange
        capture_map[i] = TextRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=node.start_point,
            end_point=node.end_point,
        )
        # capture_name 以 "." 分割表示语义层级
        parts = capture_name.split(".")
        match parts:
            # 带具体符号类型的定义捕获
            case [scoping, "definition", sym]:
                local_def_captures.append(LocalDefCapture(
                    index=i, symbol=sym, scoping=Scoping(scoping)))
            # 无具体符号类型的定义捕获
            case [scoping, "definition"]:
                local_def_captures.append(LocalDefCapture(
                    index=i, symbol=None, scoping=Scoping(scoping)))
            # 本地引用捕获
            case ["local", "reference"]:
                local_ref_captures.append(LocalRefCapture(index=i, symbol=None))
            # 作用域捕获
            case ["local", "scope"]:
                local_scope_capture_indices.append(i)
            # import 语句整体捕获
            case ["local", "import", "statement"]:
                local_import_stmt_capture_indices.append(i)
            # import 语句的组成部分（module / alias / name）
            case ["local", "import", part]:
                local_import_part_captures.append(LocalImportPartCapture(index=i, part=part))

    # 根作用域对应整个文件
    root_range = TextRange(
        start_byte=root_node.start_byte,
        end_byte=root_node.end_byte,
        start_point=root_node.start_point,
        end_point=root_node.end_point,
    )
    scope_graph = ScopeGraph(root_range, src_bytes=src_bytes)

    # 插入所有局部作用域
    for i in local_scope_capture_indices:
        scope_graph.insert_local_scope(LocalScope(capture_map[i]))

    # 构造并插入 import 语句
    for i in local_import_stmt_capture_indices:
        range = capture_map[i]
        from_name, aliases, names = "", [], []
        # 解析属于该 import statement 的所有子部分
        for part in local_import_part_captures:
            part_range = capture_map[part.index]
            if range.contains(part_range):
                match part.part:
                    case ImportPartType.MODULE:
                        from_name = parse_from(src_bytes, part_range)
                    case ImportPartType.ALIAS:
                        aliases.append(parse_alias(src_bytes, part_range))
                    case ImportPartType.NAME:
                        names.append(parse_name(src_bytes, part_range))

        import_stmt = LocalImportStmt(
            range, names, from_name=from_name, aliases=aliases
        )
        scope_graph.insert_local_import(import_stmt)

    # 插入所有定义节点（区分作用域类型）
    for def_capture in local_def_captures:
        range = capture_map[def_capture.index]
        local_def = LocalDef(range, src_bytes, def_capture.symbol)
        match def_capture.scoping:
            case Scoping.GLOBAL:
                scope_graph.insert_global_def(local_def)
            case Scoping.HOISTED:
                scope_graph.insert_hoisted_def(local_def)
            case Scoping.LOCAL:
                scope_graph.insert_local_def(local_def)

    # 插入所有引用节点
    for local_ref_capture in local_ref_captures:
        range = capture_map[local_ref_capture.index]
        # 仅当符号属于预定义命名空间类型时才记录 symbol_id
        symbol_id = local_ref_capture.symbol if local_ref_capture.symbol in NAMESPACES[language] else None
        new_ref = Reference(range, src_bytes, symbol_id=symbol_id)
        scope_graph.insert_ref(new_ref)

    return scope_graph
