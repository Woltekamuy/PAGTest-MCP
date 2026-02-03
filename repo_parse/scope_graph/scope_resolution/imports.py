"""
本模块定义了与源码 import 语句解析相关的基础工具函数与数据结构。

主要用途：
- 从源码字节缓冲区中解析标识符、别名与模块名
- 表示单条 import / from-import 语句的本地抽象结构
- 为后续依赖分析、作用域建模、符号绑定提供中间表示（IR）

"""

from dataclasses import dataclass, asdict
from typing import Optional, List

from repo_parse.scope_graph.utils import TextRange

from .graph_types import NodeKind


def parse_from(buffer: bytearray, range: TextRange) -> str:
    return buffer[range.start_byte : range.end_byte].decode("utf-8")

def parse_alias(buffer: bytearray, range: TextRange):
    return buffer[range.start_byte : range.end_byte].decode("utf-8")

def parse_name(buffer: bytearray, range: TextRange):
    return buffer[range.start_byte : range.end_byte].decode("utf-8")


class LocalImportStmt:
    """
    表示一条本地 import 语句的抽象结构。

    该结构统一表示以下形式：
    - import a, b
    - import a as x
    - from m import a, b
    - from m import a as x

    用途：
    - 构建依赖关系
    - 作用域中的符号引入
    - import 语句的字符串化与调试输出
    """

    def __init__(
        self,
        range: TextRange,
        names: List[str],
        from_name: Optional[str] = "",
        aliases: Optional[List[str]] = [],
    ):
        """
        初始化一条本地 import 语句描述。

        :param range: import 语句在源码中的整体文本范围
        :param names: 被导入的名称列表
        :param from_name: from 子句中的模块名（若不存在则为空）
        :param aliases: 与 names 对应的别名列表（可为空）
        """
        self.range = range
        self.names = names
        self.from_name = from_name
        self.aliases = aliases

    def __str__(self):
        """
        将 import 语句还原为接近源码形式的字符串表示。

        :return: import 语句的字符串表示
        """
        from_name = f"from {self.from_name} " if self.from_name else ""
        alias_str = f" as {self.aliases}" if self.aliases else ""

        names = ", ".join(self.names)

        return f"{from_name}import {names}{alias_str}"
