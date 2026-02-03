# ============================================================
# Tree-sitter Capture 数据模型定义
# ------------------------------------------------------------
# 本模块定义了一组用于承载 tree-sitter query 捕获结果的
# 轻量级数据结构（基于 pydantic.BaseModel）。
#
# 这些 Capture 对象作为“语法层 → 语义层”的中间表示，
# 被用于后续 ScopeGraph 的构建过程。
# ============================================================

from pydantic import BaseModel
from typing import Optional
from enum import Enum

from repo_parse.scope_graph.scope_resolution import Scoping


class LocalDefCapture(BaseModel):
    """
    本地定义（Definition）的捕获结果。

    表示在 tree-sitter 查询中匹配到的一个“定义”节点，
    例如类、函数、变量等。
    """

    # 捕获在 query.captures 中的索引位置
    index: int

    # 定义的符号类型（如 class / function），可能为空
    symbol: Optional[str]

    # 定义的作用域语义（GLOBAL / LOCAL / HOISTED）
    scoping: Scoping


class LocalRefCapture(BaseModel):
    """
    本地引用（Reference）的捕获结果。

    表示在代码中对某个符号的使用位置。
    """

    # 捕获在 query.captures 中的索引位置
    index: int

    # 引用的符号类型（在部分语言或场景下可能为空）
    symbol: Optional[str]


class ImportPartType(str, Enum):
    """
    import 语句中不同组成部分的类型枚举。

    用于区分同一条 import 语句中的不同语法片段。
    """

    # import / from 中的模块路径部分
    MODULE = "module"

    # as 语句中的别名部分
    ALIAS = "alias"

    # 实际被导入的名称
    NAME = "name"


class LocalImportPartCapture(BaseModel):
    """
    import 语句中某一组成部分的捕获结果。

    用于在后续阶段将 module / name / alias
    重新组合成完整的 LocalImportStmt。
    """

    # 捕获在 query.captures 中的索引位置
    index: int

    # 捕获的 import 组成部分类型（MODULE / ALIAS / NAME）
    part: str
