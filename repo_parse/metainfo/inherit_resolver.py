"""
继承关系解析器模块

该模块负责解析和管理Java代码库中的类继承关系，构建继承树和兄弟关系网络。
提供高效的血缘关系查询功能，支持代码分析、重构建议和架构理解等场景。

主要功能：
1. 从类元信息构建完整的继承关系树
2. 解析并存储兄弟类关系（共享同一父类的类）
3. 提供多层次的血缘关系查询接口
4. 支持继承关系数据的持久化存储和加载
5. 高效获取祖先、后代和兄弟关系

核心类：
- inherit_resolver: 继承关系解析器主类

数据模型：
    inherit_relations: List[Tuple[str, str]] - (子类, 父类) 关系对列表
    childs: Dict[str, List[str]] - 父类到子类列表的映射
    parents: Dict[str, str] - 子类到父类的映射
    brother_relations: Dict[str, List[str]] - 类到兄弟类列表的映射

"""

import json
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from repo_parse.config import BROTHER_RELATIONS_PATH, CLASS_METAINFO_PATH, INHERIT_TREE_PATH
from repo_parse.utils.data_processor import load_json


class inherit_resolver:
    """
    继承关系解析器

    负责从类元信息中提取和构建继承关系，包括：
    - 父子继承关系
    - 兄弟类关系（共享同一父类的类）
    - 多层次的祖先和后代关系

    属性：
        class_metainfo_path (str): 类元信息文件路径
        brother_relations_path (str): 兄弟关系数据文件路径
        inherit_tree_path (str): 继承树数据文件路径
        inherit_relations (List[Tuple[str, str]]): 继承关系列表，格式为[(子类, 父类), ...]
        childs (Dict[str, List[str]]): 父类到子类列表的映射
        parents (Dict[str, str]): 子类到父类的映射
        brother_relations (Dict[str, List[str]]): 兄弟类关系映射
        class_metainfo (list): 加载的类元信息数据

    初始化流程：
        1. 尝试从持久化文件加载继承树数据
        2. 如果加载失败，则从原始类元信息重新构建
        3. 构建完成后自动保存到文件
    """

    def __init__(
            self,
            repo_config=None,
            class_metainfo_path: str = CLASS_METAINFO_PATH,
            brother_relations_path: str = BROTHER_RELATIONS_PATH,
            inherit_tree_path: str = INHERIT_TREE_PATH,
    ):
        """
        初始化继承关系解析器

        参数：
            repo_config: 仓库配置对象，包含文件路径配置
            class_metainfo_path: 类元信息文件路径，默认使用配置路径
            brother_relations_path: 兄弟关系数据文件路径，默认使用配置路径
            inherit_tree_path: 继承树数据文件路径，默认使用配置路径

        流程：
            1. 设置文件路径（优先使用repo_config中的配置）
            2. 初始化数据结构
            3. 尝试加载已持久化的继承树数据
            4. 如果加载失败，则重新构建继承树
        """
        # 使用自定义配置覆盖默认配置
        if repo_config is not None:
            self.class_metainfo_path = repo_config.CLASS_METAINFO_PATH
            self.brother_relations_path = repo_config.BROTHER_RELATIONS_PATH
            self.inherit_tree_path = repo_config.INHERIT_TREE_PATH
        else:
            self.class_metainfo_path = class_metainfo_path
            self.brother_relations_path = brother_relations_path
            self.inherit_tree_path = inherit_tree_path

        # 初始化数据结构
        self.inherit_relations: List[Tuple[str, str]] = []  # (子类, 父类) 关系列表
        self.childs: Dict[str, List[str]] = defaultdict(list)  # 父类 -> [子类列表]
        self.parents: Dict[str, str] = {}  # 子类 -> 父类
        self.brother_relations: Dict[str, List[str]] = {}  # 类 -> [兄弟类列表]

        # 尝试加载持久化的继承树数据
        if self.load_inherit_tree():
            print("继承树数据已从持久化文件加载")
        else:
            # 加载失败，重新构建继承树
            self.class_metainfo = load_json(self.class_metainfo_path)
            self.build_inherit_tree()  # 构建继承关系
            self.resolve_brother_relation()  # 解析兄弟关系
            self.save_inherit_tree()  # 保存到文件

    def load_inherit_tree(self) -> bool:
        """
        从文件加载继承树数据

        返回：
            bool: 加载是否成功

        异常处理：
            文件不存在时返回False，其他异常会向上抛出
        """
        try:
            with open(self.inherit_tree_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 加载各个数据结构
                self.inherit_relations = [tuple(rel) for rel in data.get('inherit_relations', [])]
                self.childs = defaultdict(list, data.get('childs', {}))
                self.parents = data.get('parents', {})
                self.brother_relations = data.get('brother_relations', {})
            return True
        except FileNotFoundError:
            # 文件不存在，需要重新构建
            return False
        except json.JSONDecodeError as e:
            # JSON解析错误，记录日志并返回False
            print(f"继承树文件格式错误: {e}")
            return False

    def save_inherit_tree(self) -> None:
        """
        保存继承树数据到文件

        将当前内存中的继承关系数据序列化为JSON格式保存到文件。
        保存的数据包括：
            - inherit_relations: 继承关系列表
            - childs: 父子关系映射
            - parents: 父类映射
            - brother_relations: 兄弟关系映射
        """
        data = {
            'inherit_relations': self.inherit_relations,
            'childs': dict(self.childs),  # 转换defaultdict为普通dict
            'parents': self.parents,
            'brother_relations': self.brother_relations
        }
        with open(self.inherit_tree_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def save_json(self, file_path: str, data: dict) -> None:
        """
        通用JSON保存方法

        参数：
            file_path: 目标文件路径
            data: 要保存的数据字典
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def build_inherit_tree(self) -> None:
        """
        从类元信息构建继承树

        遍历所有类元信息，提取继承关系并构建：
            - inherit_relations: (子类, 父类) 关系对
            - childs: 父类到子类列表的映射
            - parents: 子类到父类的映射

        注意：只处理有父类的类（排除Object等根类）
        """
        for class_info in self.class_metainfo:
            class_name = class_info['name']
            parent_name = class_info['superclasses']

            # 只处理有父类的继承关系
            if parent_name:
                self.inherit_relations.append((class_name, parent_name))
                self.childs[parent_name].append(class_name)
                self.parents[class_name] = parent_name

    def resolve_brother_relation(self, save: bool = True) -> None:
        """
        解析兄弟类关系

        基于已构建的继承树，找出所有共享同一父类的类（兄弟类）。

        参数：
            save: 是否将兄弟关系保存到文件，默认为True

        逻辑：
            1. 遍历childs字典，找到有多个子类的父类
            2. 为每个子类建立兄弟关系列表
            3. 排除自身，避免自引用
        """
        for parent, children in self.childs.items():
            # 只有多个子类时才存在兄弟关系
            if len(children) < 2:
                continue

            for child in children:
                # 初始化兄弟列表
                if child not in self.brother_relations:
                    self.brother_relations[child] = []

                # 添加其他子类作为兄弟
                for sibling in children:
                    if sibling != child:
                        self.brother_relations[child].append(sibling)

        # 可选：保存兄弟关系到独立文件
        if save:
            self.save_json(self.brother_relations_path, self.brother_relations)

    def get_brothers(self, class_name: str) -> List[str]:
        """
        获取指定类的所有兄弟类

        参数：
            class_name: 目标类名

        返回：
            List[str]: 兄弟类名列表，如果没有兄弟则返回空列表
        """
        return self.brother_relations.get(class_name, [])

    def get_brothers_and_parent(self, class_name: str) -> Optional[Tuple[str, List[str]]]:
        """
        获取指定类的父类和兄弟类

        参数：
            class_name: 目标类名

        返回：
            Optional[Tuple[str, List[str]]]: (父类名, 兄弟类列表) 元组
                如果类不存在或无父类，返回None

        注意：此方法实现有误，childs是字典，需要遍历查找
        """
        # 修复：正确遍历childs字典查找类所在的父类
        for parent, children in self.childs.items():
            if class_name in children:
                brothers = [child for child in children if child != class_name]
                return parent, brothers
        return None

    def get_parent(self, class_name: str) -> Optional[str]:
        """
        获取指定类的直接父类

        参数：
            class_name: 目标类名

        返回：
            Optional[str]: 父类名，如果不存在父类则返回None
        """
        return self.parents.get(class_name, None)

    def get_ancestors(self, class_name: str) -> List[str]:
        """
        获取指定类的所有祖先类（包括直接父类、祖父类等）

        参数：
            class_name: 目标类名

        返回：
            List[str]: 祖先类名列表，按从近到远的顺序排列

        示例：
            如果 C 继承 B，B 继承 A，则 get_ancestors("C") 返回 ["B", "A"]
        """
        ancestors = []
        current = class_name

        # 沿着继承链向上查找
        while current in self.parents:
            parent = self.parents[current]
            ancestors.append(parent)
            current = parent

        return ancestors

    def get_children(self, class_name: str) -> List[str]:
        """
        获取指定类的直接子类

        参数：
            class_name: 目标类名

        返回：
            List[str]: 直接子类名列表
        """
        return self.childs.get(class_name, [])

    def get_all_descendants(self, class_name: str) -> List[str]:
        """
        获取指定类的所有后代类（递归获取所有子类、孙子类等）

        参数：
            class_name: 目标类名

        返回：
            List[str]: 所有后代类名列表，使用深度优先遍历

        算法：递归深度优先搜索
        """
        descendants = []
        direct_children = self.get_children(class_name)
        descendants.extend(direct_children)

        # 递归获取所有后代
        for child in direct_children:
            descendants.extend(self.get_all_descendants(child))

        return descendants