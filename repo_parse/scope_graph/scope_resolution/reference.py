"""
本模块定义了用于表示源码中“符号引用（Reference）”的数据结构。

Reference 通常用于：
- 表示变量、函数、类等符号在源码中的一次引用
- 记录引用在源码中的精确位置（TextRange）
- 将引用与解析得到的符号唯一标识（SymbolId）进行关联

"""

from typing import Optional
from dataclasses import dataclass

from repo_parse.scope_graph.utils import SymbolId, TextRange


@dataclass
class Reference:
    """
    表示一次符号引用。

    属性说明：
    - range：该引用在源码中的文本范围
    - symbol_id：解析后绑定的符号唯一标识（可能为空，表示尚未解析）
    - name：从源码 buffer 中提取出的原始引用文本（如变量名）
    """

    range: TextRange
    symbol_id: Optional[SymbolId]

    def __init__(
        self,
        range: TextRange,
        buffer: bytearray,
        symbol_id: Optional[SymbolId] = None
    ) -> "Reference":
        """
        初始化 Reference 实例。

        初始化过程：
        - 保存引用的文本范围
        - 保存符号 ID（若已解析）
        - 根据 range 的字节区间，从源码 buffer 中切片并解码得到引用名称

        :param range: 引用在源码中的字节与行列范围
        :param buffer: 源码的字节数组表示
        :param symbol_id: 可选的符号唯一标识
        """
        self.range = range
        self.symbol_id = symbol_id
        # 从源码 buffer 中根据字节范围提取引用名称
        self.name = buffer[
            self.range.start_byte : self.range.end_byte
        ].decode("utf-8")
