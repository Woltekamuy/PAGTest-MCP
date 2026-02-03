"""
本模块定义了用于表示源码中“局部定义（Local Definition）”的结构。

LocalDef 通常用于：
- 表示变量、函数、类等符号的定义位置
- 从源码字节缓冲区中提取定义名称
- 转换为作用域图（scope graph）中的节点表示

"""

from dataclasses import dataclass
from typing import Optional

from repo_parse.scope_graph.utils import TextRange

from .graph_types import NodeKind


@dataclass
class LocalDef:
    """
    表示一次局部符号定义。

    属性说明：
    - range：定义在源码中的文本范围
    - symbol：定义的符号类型或分类标识（如变量 / 函数 / 类）
    - name：从源码中解析得到的定义名称
    """

    range: TextRange
    symbol: str
    name: str

    def __init__(
        self,
        range: TextRange,
        buffer: bytearray,
        symbol: Optional[str]
    ) -> "LocalDef":
        """
        初始化 LocalDef 实例。

        初始化过程：
        - 记录定义的文本范围
        - 保存符号类型信息
        - 根据文本范围从源码 buffer 中切片并解码得到定义名称

        :param range: 定义在源码中的文本范围
        :param buffer: 源码对应的字节数组
        :param symbol: 符号类型或分类标识（可选）
        """
        self.range = range
        self.symbol = symbol
        # 从源码 buffer 中根据字节范围提取定义名称
        self.name = buffer[
            self.range.start_byte : self.range.end_byte
        ].decode("utf-8")

    def to_node(self):
        """
        将当前 LocalDef 转换为作用域图节点的字典表示。

        返回结构说明：
        - name：定义名称
        - range：文本范围的字典表示（由 TextRange 提供）
        - type：节点类型，固定为 NodeKind.DEFINITION
        - data：附加元数据，用于描述定义类型

        :return: 可用于构建 scope graph 的节点字典
        """
        return {
            "name": self.name,
            "range": self.range.dict(),
            "type": NodeKind.DEFINITION,
            "data": {"def_type": self.symbol},
        }
