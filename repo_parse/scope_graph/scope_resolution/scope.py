"""
本模块定义了作用域（Scope）相关的基础数据结构与遍历工具。

主要用途：
- 描述局部作用域的文本范围
- 定义变量/符号的作用域类型（全局、提升、局部）
- 基于作用域图（scope graph）模拟变量查找时的作用域链回溯过程

"""

from dataclasses import dataclass
from typing import Optional, Iterator
from networkx import DiGraph
from enum import Enum

from repo_parse.scope_graph.utils import TextRange

from .graph_types import EdgeKind


@dataclass
class LocalScope:
    """
    表示一个局部作用域。

    当前仅包含：
    - 该作用域在源码中的文本范围（TextRange）

    该结构通常作为 scope graph 中的节点附加信息使用。
    """
    range: TextRange

    def __init__(self, range: TextRange):
        # 显式定义 __init__，便于后续扩展或插入自定义初始化逻辑
        self.range = range


class Scoping(str, Enum):
    """
    符号或定义的作用域类型枚举。

    - GLOBAL：全局作用域
    - HOISTED：提升作用域（如函数声明、某些语言的声明提升）
    - LOCAL：局部作用域
    """
    GLOBAL = "global"
    HOISTED = "hoist"
    LOCAL = "local"


class ScopeStack(Iterator):
    """
    作用域栈（Scope Stack）迭代器。

    基于 scope graph（有向图）实现，用于模拟程序执行或
    静态分析中“从当前作用域向外逐层查找”的行为。

    每次迭代：
    - 返回当前作用域节点
    - 将内部指针移动到父作用域
    """

    def __init__(self, scope_graph: DiGraph, start: Optional[int]):
        """
        初始化作用域栈。

        :param scope_graph: 表示作用域关系的有向图
        :param start: 起始作用域节点 ID（None 表示空栈）
        """
        self.scope_graph = scope_graph
        self.start = start

    def __iter__(self) -> "ScopeStack":
        """
        返回自身，使其符合 Python 迭代器协议。
        """
        return self

    # 妙啊，这个函数模拟了在程序执行时查找变量定义时的行为，从当前作用域逐层向外查找定义或导入。
    # TODO: fix the start parameter to return the root of the graph if not provided
    def __next__(self) -> int:
        """
        返回当前作用域节点，并推进到其父作用域。

        实现逻辑：
        - 从当前作用域节点出发
        - 查找一条类型为 ScopeToScope 的出边
        - 将目标节点视为父作用域
        - 若不存在父作用域，则在下一次调用时终止迭代

        :return: 当前作用域节点 ID
        :raises StopIteration: 当作用域链遍历结束时
        """
        if self.start is not None:
            original = self.start
            parent = None
            for _, target, attrs in self.scope_graph.out_edges(self.start, data=True):
                if (
                    attrs.get("type") == EdgeKind.ScopeToScope
                ):  # Replace with appropriate edge kind check
                    parent = target
                    break
            # 将起始节点推进到父作用域，供下一次迭代使用
            self.start = parent
            return original
        else:
            raise StopIteration
