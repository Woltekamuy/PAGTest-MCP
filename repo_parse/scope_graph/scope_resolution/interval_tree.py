"""
本模块定义了作用域（Scope）的轻量级表示。

主要用途：
- 将 TextRange 映射为行级作用域区间
- 为作用域绑定唯一的图节点标识（node_id）
- 作为 scope graph 或作用域分析过程中的基础数据结构
"""

from repo_parse.scope_graph.utils import TextRange

epsilon = 0.1


class Scope:
    """
    表示一个作用域节点的简化模型。

    属性说明：
    - start / end：作用域覆盖的起始行号与结束行号（闭区间）
    - node_id：该作用域在作用域图（scope graph）中的唯一节点标识
    """

    def __init__(self, range: TextRange, node_id: str):
        """
        初始化作用域对象。

        初始化过程：
        - 从 TextRange 中提取行号范围
        - 绑定作用域对应的图节点 ID

        :param range: 作用域在源码中的文本范围
        :param node_id: 作用域在图结构中的唯一标识
        """
        # 将文本范围转换为行级作用域区间
        self.start, self.end = range.line_range()

        # 作用域在 scope graph 中对应的节点 ID
        self.node_id = node_id
