"""
本模块定义了若干用于代码作用域分析（scope graph）与源码结构建模的
基础数据结构与工具类。

主要内容包括：
1. 文本位置与范围建模（Point / TextRange）
2. 文件路径处理辅助函数
3. 系统模块与第三方模块的加载、校验与维护
4. 统一的日志记录与异常处理策略

该模块通常作为语法树分析、依赖分析、符号解析等功能的基础组件。
"""

from pydantic import BaseModel

from dataclasses import dataclass
from typing import NamedTuple, TypeAlias, Tuple, List
import json
from repo_parse.scope_graph.config import SYS_MODULES_LIST, THIRD_PARTY_MODULES_LIST
from pathlib import Path

from logging import getLogger

# 模块级 logger，用于记录配置加载与 IO 异常
logger = getLogger(__name__)

# 符号唯一标识的类型别名（如变量、函数、类的 ID）
SymbolId: TypeAlias = str


class Point(NamedTuple):
    """
    表示源码中的一个二维坐标点（行号 + 列号）。

    通常用于语法树节点、文本范围等位置描述。
    """
    row: int
    column: int


class TextRange(BaseModel):
    """
    表示源码中的一个连续文本区间。

    同时支持：
    - 字节级范围（start_byte / end_byte）
    - 行列级范围（start_point / end_point）

    该结构适用于：
    - AST 节点范围判断
    - 代码块包含关系分析
    - 行级 / 字节级精确定位
    """

    start_byte: int
    end_byte: int
    start_point: Point
    end_point: Point

    def __init__(
        self,
        *,
        start_byte: int,
        end_byte: int,
        start_point: Tuple[int, int],
        end_point: Tuple[int, int],
    ):
        """
        初始化 TextRange。

        注意：
        - start_point / end_point 使用 (row, column) 元组传入
        - 实际存储时由 Pydantic 自动转换为 Point 类型
        """
        super().__init__(
            start_byte=start_byte,
            end_byte=end_byte,
            start_point=start_point,
            end_point=end_point,
        )

    def line_range(self):
        """
        获取该文本范围覆盖的行号区间。

        :return: (起始行号, 结束行号)
        """
        return self.start_point.row, self.end_point.row

    def contains(self, range: "TextRange"):
        """
        判断当前范围是否在字节级别完全包含另一个范围。

        :param range: 待判断的 TextRange
        :return: True 表示完全包含
        """
        return range.start_byte >= self.start_byte and range.end_byte <= self.end_byte

    def contains_line(self, range: "TextRange", overlap=False):
        """
        判断当前范围是否在行级别包含或覆盖另一个范围。

        :param range: 待判断的 TextRange
        :param overlap:
            - False：要求完全包含（严格区间）
            - True：允许任意行号重叠
        :return: True 表示满足条件
        """
        if overlap:
            return (
                range.start_point.row >= self.start_point.row
                and range.start_point.row <= self.end_point.row
            ) or (
                range.end_point.row <= self.end_point.row
                and range.end_point.row >= self.start_point.row
            )

        return (
            range.start_point.row >= self.start_point.row
            and range.end_point.row <= self.end_point.row
        )


def get_shortest_subpath(path: Path, root: Path) -> Path:
    """
    获取相对于给定根路径的最短相对路径。

    常用于：
    - 统一路径表示
    - 生成与项目根目录相关的文件标识

    :param path: 目标路径
    :param root: 根路径
    :return: 相对路径
    """
    return path.relative_to(root)


class SysModules:
    """
    系统模块集合封装类。

    用途：
    - 加载预定义的系统模块列表（如 Python 内置模块）
    - 提供模块是否为系统模块的快速判断接口
    """

    def __init__(self, lang):
        """
        初始化系统模块列表。

        :param lang: 语言标识（当前实现中未使用，预留扩展）
        """
        try:
            sys_mod_file = open(SYS_MODULES_LIST, "r")
            self.sys_modules = json.loads(sys_mod_file.read())
        except Exception as e:
            logger.error(f"Error loading system modules: {e}")
            self.sys_modules = []

    def __iter__(self):
        """
        允许直接对 SysModules 实例进行迭代。
        """
        return iter(self.sys_modules)

    def check(self, module_name):
        """
        判断给定模块名是否属于系统模块。

        :param module_name: 模块名称
        :return: True 表示是系统模块
        """
        return module_name in self.sys_modules


class ThirdPartyModules:
    """
    第三方模块集合封装类。

    用途：
    - 维护项目中使用的第三方依赖模块列表
    - 支持查询、迭代与动态更新
    - 将更新结果持久化回配置文件
    """

    def __init__(self, lang):
        """
        初始化第三方模块列表。

        :param lang: 语言标识（当前实现中主要用于语义区分）
        """
        self.lang = lang
        try:
            with open(THIRD_PARTY_MODULES_LIST, "r") as file:
                self.third_party_modules = json.loads(file.read())["modules"]
        except Exception as e:
            logger.error(f"Error loading third party modules: {e}")
            self.third_party_modules = []

    def check(self, module_name):
        """
        判断给定模块名是否为第三方模块。

        :param module_name: 模块名称
        :return: True 表示是第三方模块
        """
        return module_name in self.third_party_modules

    def __iter__(self):
        """
        允许直接对 ThirdPartyModules 实例进行迭代。
        """
        return iter(self.third_party_modules)

    def update(self, new_modules: List[str]):
        """
        向第三方模块列表中追加新模块，并写回配置文件。

        :param new_modules: 新增的第三方模块名列表
        """
        self.third_party_modules.extend(new_modules)
        try:
            with open(THIRD_PARTY_MODULES_LIST, "w") as file:
                json.dump({"modules": self.third_party_modules}, file, indent=4)
        except Exception as e:
            logger.error(f"Error writing third party modules: {e}")
