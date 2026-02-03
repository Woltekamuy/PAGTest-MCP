"""
- InterfaceResolver: 接口关系解析器

数据结构：
    interface_map: 接口名到接口详情的字典映射
    result: 包含接口完整信息的字典列表，每个接口包含：
        - uris: 接口唯一标识
        - name: 接口名称
        - methods: 接口所有方法签名（包括继承的）
        - implementations: 实现该接口的类URI列表

"""

from repo_parse.config import INTERFACE_BROTHER_RELATIONS_PATH
from repo_parse.utils.data_processor import save_json


class InterfaceResolver:
    """
    接口关系解析器

    负责解析接口的继承关系和实现关系，包括：
    1. 递归收集接口的所有方法（包括从父接口继承的方法）
    2. 识别实现特定接口的所有类
    3. 构建接口与实现类之间的完整关系网络

    属性：
        class_metainfo (list): 类元信息列表
        interface_metainfo (list): 接口元信息列表

    注意：接口兄弟关系指的是共享相同接口实现关系的类，
          这些类可以被视为具有共同的"接口血缘关系"。
    """

    def __init__(self, class_metainfo, interface_metainfo):
        """
        初始化接口关系解析器

        参数：
            class_metainfo: 类元信息列表，包含所有类的详细信息
            interface_metainfo: 接口元信息列表，包含所有接口的详细信息
        """
        self.class_metainfo = class_metainfo
        self.interface_metainfo = interface_metainfo

    def resolve_interface_brother_relation(
            self,
            save: bool = True,
            interface_brother_relations_path: str = INTERFACE_BROTHER_RELATIONS_PATH
    ) -> list:
        """
        解析接口兄弟关系

        该方法执行以下核心操作：
        1. 为每个接口递归收集所有方法（包括继承的方法）
        2. 查找实现每个接口的所有类
        3. 构建接口完整信息字典
        4. 可选地保存结果到文件

        参数：
            save: 是否将结果保存到JSON文件，默认为True
            interface_brother_relations_path: 保存文件的路径

        返回：
            list: 接口信息字典列表，每个字典包含：
                - uris: 接口唯一标识符
                - name: 接口名称
                - methods: 接口的所有方法签名列表
                - implementations: 实现该接口的类URI列表

        处理流程：
            1. 构建接口名到接口详情的快速映射
            2. 递归收集每个接口的方法（处理接口继承）
            3. 查找所有实现该接口的类
            4. 构建接口完整信息
            5. 可选保存到文件
        """
        # 构建接口名到接口详情的映射，便于快速查找
        interface_map = {interface['name']: interface for interface in self.interface_metainfo}

        def collect_methods(interface_name, visited=None):
            """
            递归收集接口的所有方法（包括继承的方法）

            使用深度优先遍历接口继承树，收集所有方法签名。

            参数：
                interface_name: 当前接口名称
                visited: 已访问的接口集合，用于检测循环依赖

            返回：
                list: 方法签名列表（已去重，但本实现未去重，可优化）

            注意：本函数为内部嵌套函数，用于递归收集方法
            """
            if visited is None:
                visited = set()

            # 检测循环依赖，防止无限递归
            if interface_name in visited:
                return []
            visited.add(interface_name)

            # 获取接口详情
            interface = interface_map.get(interface_name)
            if not interface:
                return []

            methods = []
            # 收集当前接口声明的方法
            for method in interface.get('methods', []):
                # 处理方法签名字符串，提取方法名部分
                # 格式如："package.ClassName.methodName(params)"
                method_parts = method.split('.')
                method_signature = method_parts[-1] if method_parts else method
                methods.append(method_signature)

            # 递归收集父接口的方法
            for parent_interface in interface.get('superclasses', []):
                parent_interface_name = self.get_interface_name_by_uri(parent_interface)
                if parent_interface_name:
                    parent_methods = collect_methods(parent_interface_name, visited)
                    methods.extend(parent_methods)

            return methods

        result = []
        # 处理每个接口
        for interface in self.interface_metainfo:
            interface_name = interface['name']

            # 1. 收集接口的所有方法（递归包括父接口）
            all_methods = collect_methods(interface_name)

            # 2. 查找实现该接口的所有类
            implementing_classes = []
            for cls in self.class_metainfo:
                # 检查类是否实现了当前接口
                if interface_name in cls.get('super_interfaces', []):
                    implementing_classes.append(cls['uris'])

            # 3. 构建接口完整信息字典
            interface_dict = {
                "uris": interface['uris'],  # 接口唯一标识
                "name": interface_name,  # 接口名称
                "methods": all_methods,  # 接口所有方法签名
                "implementations": implementing_classes  # 实现类的URI列表
            }
            result.append(interface_dict)

        # 4. 可选：保存结果到JSON文件
        if save:
            save_json(file_path=interface_brother_relations_path, data=result)

        return result

    def get_interface_name_by_uri(self, uri: str) -> str:
        """
        根据接口URI获取接口名称

        在接口元信息中查找与给定URI匹配的接口，返回其名称。

        参数：
            uri: 接口的唯一标识符

        返回：
            str: 接口名称，如果未找到则返回None

        使用场景：
            用于将父接口的URI转换为接口名称，便于后续处理
        """
        for interface in self.interface_metainfo:
            if interface['uris'] == uri:
                return interface['name']
        return None