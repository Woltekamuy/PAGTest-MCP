"""
本模块定义了作用域图（Scope Graph）中使用的核心类型与枚举。

主要内容包括：
1. 节点类型（NodeKind）的枚举定义
2. 边类型（EdgeKind）的枚举定义
3. 作用域节点（ScopeNode）的结构描述
4. 作用域节点 ID 的类型别名（ScopeID）

该模块为 scope graph 的结构建模提供统一的类型基础，
被广泛用于作用域分析、符号绑定与引用解析等阶段。
"""

from typing import Dict, Optional, NewType
from enum import Enum

from repo_parse.scope_graph.graph import Node
from repo_parse.scope_graph.utils import TextRange


class NodeKind(str, Enum):
    """
    Scope Graph 中节点类型的枚举定义。

    不同节点类型表示源码中不同语义实体：
    - SCOPE：局部作用域节点
    - DEFINITION：符号定义节点
    - IMPORT：import 语句节点
    - REFERENCE：符号引用节点
    """
    SCOPE = "LocalScope"
    DEFINITION = "LocalDef"
    IMPORT = "Import"
    REFERENCE = "Reference"


class EdgeKind(str, Enum):
    """
    Scope Graph 中边类型的枚举定义。

    不同边类型表示节点之间的语义关系：
    - ScopeToScope：作用域之间的父子关系
    - DefToScope：定义所属作用域
    - ImportToScope：import 语句所属作用域
    - RefToDef：引用绑定到定义
    - RefToOrigin：引用指向原始定义（跨作用域/文件）
    - RefToImport：引用通过 import 解析得到
    """
    ScopeToScope = "ScopeToScope"
    DefToScope = "DefToScope"
    ImportToScope = "ImportToScope"
    RefToDef = "RefToDef"
    RefToOrigin = "RefToOrigin"
    RefToImport = "RefToImport"


class ScopeNode(Node):
    """
    作用域图中的节点基类扩展。

    在通用 Node 基础上，补充了：
    - range：该节点在源码中的文本范围
    - type：节点类型（NodeKind）
    - name：节点名称（如符号名、模块名等，可选）
    - data：附加的结构化元数据（可选）

    该类通常作为具体节点类型（Scope / Def / Import / Reference）的
    统一承载结构。
    """
    range: TextRange
    type: NodeKind
    name: Optional[str] = ""
    data: Optional[Dict] = {}


# 作用域节点 ID 的强类型别名
ScopeID = NewType("ScopeID", int)