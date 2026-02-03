"""
潜在兄弟关系解析器模块

主要功能：
1. 计算类之间的结构相似度（基于方法集合的Jaccard相似度）
2. 识别潜在的结构相似类（即使它们没有继承关系）
3. 构建基于相似度的类关系网络
4. 支持相似度阈值配置，灵活控制识别粒度

核心类：
- PotentialBrotherResolver: 潜在兄弟关系解析器

算法原理：
    使用Jaccard相似度算法：J(A,B) = |A∩B| / |A∪B|
    其中A和B分别为两个类的方法集合
    相似度范围：[0, 1]，1表示完全相同的结构

数据模型：
    class_to_methods: 类名到方法集合的映射
    superclass_to_classes: 父类到子类集合的映射
    class_to_superclass: 子类到父类的映射
    potential_brothers: 类到相似类集合的映射
"""

import json
from collections import defaultdict
from typing import List, Dict, Set, Tuple
from itertools import combinations

from repo_parse.config import POTENTIAL_BROTHER_RELATIONS_PATH
from repo_parse.utils.data_processor import save_json


class PotentialBrotherResolver:
    """
    潜在兄弟关系解析器

    基于类的方法结构相似性，识别可能具有相似功能或设计的类，
    即使它们没有直接的继承关系。这种关系可以帮助发现：
    1. 重复的实现
    2. 相似的设计模式
    3. 重构机会

    属性：
        class_metainfo (List[Dict]): 类元信息列表

    主要数据结构：
        potential_brothers: Dict[str, List[str]] - 类名到相似类列表的映射
    """

    def __init__(self, class_metainfo: List[Dict]):
        """
        初始化潜在兄弟关系解析器

        参数：
            class_metainfo: 类元信息列表，每个字典包含类的详细信息，
                            特别是'name'和'methods'字段
        """
        self.class_metainfo = class_metainfo

    def jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """
        计算两个集合的Jaccard相似度

        Jaccard相似度公式：J(A,B) = |A∩B| / |A∪B|
        用于衡量两个集合的相似程度，值范围0到1

        参数：
            set1: 第一个集合
            set2: 第二个集合

        返回：
            float: 相似度值，0表示完全不同，1表示完全相同

        示例：
            set1 = {"methodA", "methodB"}
            set2 = {"methodA", "methodC"}
            J = 1/3 ≈ 0.333

        注意：
            当两个集合都为空时，返回0.0
        """
        intersection = set1.intersection(set2)  # 交集
        union = set1.union(set2)  # 并集

        if not union:  # 防止除零错误
            return 0.0

        return len(intersection) / len(union)

    def resolve_potential_brothers(
            self,
            similarity_threshold: float = 1.0,
            save: bool = True,
            potential_brother_relations_path: str = POTENTIAL_BROTHER_RELATIONS_PATH
    ) -> Dict[str, List[str]]:
        """
        解析潜在的兄弟关系

        基于类的方法集合相似度，识别结构相似的类作为潜在兄弟。
        排除已有继承关系的类（真正的兄弟类）。

        参数：
            similarity_threshold: 相似度阈值，默认1.0（完全相同的结构）
                                取值范围：0.0 ~ 1.0
                                值越小，识别的类越多（更宽松）
                                值越大，识别的类越少（更严格）
            save: 是否将结果保存到JSON文件，默认为True
            potential_brother_relations_path: 保存文件的路径

        返回：
            Dict[str, List[str]]: 潜在兄弟关系字典
                键：类名
                值：相似类名列表（按字母顺序排序）

        处理流程：
            1. 构建继承关系映射（排除真正的兄弟类）
            2. 构建类到方法的映射
            3. 对所有类进行两两组合比较
            4. 计算Jaccard相似度
            5. 过滤达到阈值的类对
            6. 构建关系字典并可选保存

        注意：
            - 排除已有共同父类的类（它们已经是真正的兄弟）
            - 相似度阈值=1.0时，只识别方法集合完全相同的类
            - 相似度阈值=0.5时，识别方法集合有50%以上相同的类
        """
        # 1. 构建继承关系映射
        superclass_to_classes = defaultdict(set)  # 父类 -> 子类集合
        class_to_superclass = {}  # 子类 -> 父类

        for cls in self.class_metainfo:
            class_name = cls.get('name')
            superclasses = cls.get('superclasses', [])

            # 规范化父类信息（处理多种格式）
            if isinstance(superclasses, str):
                # 字符串类型：非空字符串转为列表，空字符串转为[""]
                superclasses = [superclasses] if superclasses.strip() else [""]
            elif isinstance(superclasses, list):
                # 列表类型：确保非空列表，空列表转为[""]
                superclasses = superclasses if superclasses else [""]
            else:
                # 其他类型：转为空父类
                superclasses = [""]

            # 取第一个父类作为主要父类（假设单继承）
            parent_class = superclasses[0] if superclasses else ""

            superclass_to_classes[parent_class].add(class_name)
            class_to_superclass[class_name] = parent_class

        # 2. 构建类到方法的映射
        class_to_methods = {}  # 类名 -> 方法集合

        for cls in self.class_metainfo:
            class_name = cls.get('name')
            methods = set(cls.get('methods', []))  # 转换为集合便于计算
            class_to_methods[class_name] = methods

        # 3. 识别潜在兄弟关系
        potential_brothers = defaultdict(set)  # 类名 -> 相似类集合
        all_classes = [cls['name'] for cls in self.class_metainfo]

        # 遍历所有类对（组合，无序）
        for cls1, cls2 in combinations(all_classes, 2):
            # 跳过真正的兄弟类（有共同父类）
            parent1 = class_to_superclass.get(cls1, "")
            parent2 = class_to_superclass.get(cls2, "")

            if parent1 and parent1 == parent2:
                continue  # 已经是兄弟关系，跳过

            # 获取方法集合
            methods1 = class_to_methods.get(cls1, set())
            methods2 = class_to_methods.get(cls2, set())

            # 计算Jaccard相似度
            similarity = self.jaccard_similarity(methods1, methods2)

            # 如果相似度达到阈值，记录为潜在兄弟
            if similarity >= similarity_threshold:
                potential_brothers[cls1].add(cls2)
                potential_brothers[cls2].add(cls1)  # 对称关系

        # 4. 整理结果（排序并转换为列表）
        potential_brothers_dict = {
            cls: sorted(list(brothers))  # 排序保证结果一致性
            for cls, brothers in potential_brothers.items()
        }

        # 5. 可选：保存结果到JSON文件
        if save:
            save_json(
                file_path=potential_brother_relations_path,
                data=potential_brothers_dict
            )

        return potential_brothers_dict