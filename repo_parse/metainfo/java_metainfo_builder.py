"""
Java元信息构建器实现模块

本模块实现了Java语言的元信息构建器，负责将原始解析数据转换为具体的Java对象模型，
并处理Java特有的特性如接口、抽象类、记录（record）等。
同时提供兄弟关系解析、包信息解析等高级功能。
"""

from collections import defaultdict
from typing import Dict, List, Tuple
# 导入配置文件路径
from repo_parse.config import (
    ABSTRACTCLASS_METAINFO_PATH,  # 抽象类元数据输出路径
    ALL_METAINFO_PATH,  # 原始元数据输入路径
    BROTHER_RELATIONS_PATH,  # 兄弟关系输出路径
    CLASS_METAINFO_PATH,  # 普通类元数据输出路径
    FILE_IMPORTS_PATH,  # 文件导入信息输出路径
    INTERFACE_METAINFO_PATH,  # 接口元数据输出路径
    JUNIT_VERSION_PATH,  # JUnit版本信息输出路径
    METHOD_METAINFO_PATH,  # 方法元数据输出路径
    PACKAGES_METAINFO_PATH,  # 包信息输出路径
    RECORD_METAINFO_PATH,  # 记录元数据输出路径
    RESOLVED_METAINFO_PATH,  # 解析后元数据输出路径
    TESTCASE_METAINFO_PATH,  # 测试用例输出路径
    TESTCLASS_METAINFO_PATH,  # 测试类输出路径
)
# 导入基础构建器和模型
from repo_parse.metainfo.metainfo_builder import MetaInfoBuilder
from repo_parse.metainfo.model import (
    JavaAbstractClass,
    JavaClass,
    JavaInterface,
    JavaMethodSignature,
    JavaRecord,
    Method,
    TestMethod
)
# 导入工具函数
from repo_parse.utils.data_processor import load_json, save_json
from repo_parse.utils.java import get_java_standard_method_name
from repo_parse import logger


class JavaMetaInfoBuilder(MetaInfoBuilder):
    """
    Java语言元信息构建器

    继承自MetaInfoBuilder，专门处理Java语言的元数据构建。
    支持Java特有结构：接口、抽象类、记录（record）、注解等。

    扩展功能：
    1. 兄弟关系解析：找出共享同一父类的类关系
    2. 包信息解析：组织文件到包的映射
    3. 文件导入解析：提取导入语句和JUnit版本检测
    4. Java特有类型处理：接口、抽象类、记录

    新增属性：
        interfaces (List[JavaInterface]): 接口对象列表
        records (List[JavaRecord]): 记录对象列表
        abstract_classes (List[JavaAbstractClass]): 抽象类对象列表
        brother_relations_path (str): 兄弟关系文件路径
    """

    def __init__(self,
                 metainfo_json_path: str = ALL_METAINFO_PATH,
                 resolved_metainfo_path: str = RESOLVED_METAINFO_PATH,
                 brother_relations_path: str = BROTHER_RELATIONS_PATH) -> None:
        """
        初始化Java元信息构建器

        参数：
            metainfo_json_path (str): 原始元数据JSON文件路径
            resolved_metainfo_path (str): 解析后元数据保存路径
            brother_relations_path (str): 兄弟关系数据保存路径
        """
        # 调用父类初始化
        super().__init__(metainfo_json_path, resolved_metainfo_path)

        # Java特有数据结构初始化
        self.interfaces = []  # 接口列表
        self.records = []  # 记录列表（Java 14+）
        self.abstract_classes = []  # 抽象类列表

        # 兄弟关系处理相关
        self.brother_relations_path = brother_relations_path

    def save(self, path_to_data: Dict[str, List[Dict]] = None):
        """
        保存所有元数据到相应文件

        参数：
            path_to_data (Dict[str, List[Dict]]): 可选的路径到数据映射
                如果为None，使用默认的Java特有配置

        默认保存的文件类型：
            - 普通类 (CLASS_METAINFO_PATH)
            - 普通方法 (METHOD_METAINFO_PATH)
            - 测试用例 (TESTCASE_METAINFO_PATH)
            - 测试类 (TESTCLASS_METAINFO_PATH)
            - 记录 (RECORD_METAINFO_PATH)
            - 接口 (INTERFACE_METAINFO_PATH)
            - 抽象类 (ABSTRACTCLASS_METAINFO_PATH)
        """
        if path_to_data is None:
            # 默认的Java特有文件映射
            path_to_data = {
                CLASS_METAINFO_PATH: self.classes,
                METHOD_METAINFO_PATH: self.methods,
                TESTCASE_METAINFO_PATH: self.testcases,
                TESTCLASS_METAINFO_PATH: self.testclasses,
                RECORD_METAINFO_PATH: self.records,
                INTERFACE_METAINFO_PATH: self.interfaces,
                ABSTRACTCLASS_METAINFO_PATH: self.abstract_classes
            }
        # 调用父类保存方法
        self.save_metainfo(path_to_data)

    def resolve_brother_relation(self, save: bool = True):
        """
        解析兄弟关系（共享同一父类的类之间的关系）

        兄弟关系指继承自同一个父类的类之间的关系。
        这种关系对于理解代码结构、发现相似类、重构等有重要意义。

        处理流程：
            1. 从类元数据中提取继承关系
            2. 构建父类到子类的映射
            3. 找出有多个子类的父类
            4. 为这些子类建立兄弟关系

        参数：
            save (bool): 是否保存结果到文件，默认为True

        输出格式示例：
            {
                "ChildClassA": ["ChildClassB", "ChildClassC"],
                "ChildClassB": ["ChildClassA", "ChildClassC"],
                "ChildClassC": ["ChildClassA", "ChildClassB"]
            }
        """
        # 存储继承关系：子类 -> 父类 对
        inherit_relations: List[Tuple[str, str]] = []

        # 父类 -> 子类列表 映射
        childs: Dict[str, List[str]] = defaultdict(list)

        # 加载已保存的类元数据
        self.class_metainfo = load_json(file_path=CLASS_METAINFO_PATH)

        # 提取所有继承关系
        for class_info in self.class_metainfo:
            class_name = class_info['name']
            parent_names = class_info['superclasses']  # 父类列表

            for parent_name in parent_names:
                inherit_relations.append((class_name, parent_name))
                childs[parent_name].append(class_name)

        # 构建兄弟关系：共享同一父类的类互为兄弟
        brother_relations: Dict[str, List[str]] = {}

        for parent_name, children in childs.items():
            # 只有多个子类时才有兄弟关系
            if len(children) < 2:
                continue

            # 为每个子类添加兄弟
            for child in children:
                if child not in brother_relations:
                    brother_relations[child] = []

                # 添加除自己外的所有兄弟
                for sibling in children:
                    if sibling != child:
                        brother_relations[child].append(sibling)

        # 保存兄弟关系数据
        if save:
            save_json(file_path=self.brother_relations_path, data=brother_relations)

    def resolve_package_metainfo(
            self,
            file_imports_path: str = FILE_IMPORTS_PATH,
            packages_metainfo_path: str = PACKAGES_METAINFO_PATH
    ):
        """
        解析包信息，构建包到文件的映射

        在Java中，包是组织代码的重要方式。此功能：
        1. 从文件导入信息中提取包声明
        2. 构建包名到文件路径的映射
        3. 用于包级别的分析和导航

        参数：
            file_imports_path (str): 文件导入信息文件路径
            packages_metainfo_path (str): 包信息输出路径

        处理流程：
            1. 加载文件导入数据
            2. 提取每个文件的包声明（通常是第一个元素）
            3. 构建包名->[文件路径列表]映射
            4. 保存结果
        """
        # 加载文件导入信息
        self.file_imports = load_json(file_path=file_imports_path)

        # 构建包到文件的映射
        package_to_file_path = defaultdict(list)

        for file_path, imports_list in self.file_imports.items():
            # imports_list[0]通常是包声明
            if imports_list and len(imports_list) > 0:
                package_name = imports_list[0]  # 如 "package com.example;"
                package_to_file_path[package_name].append(file_path)

        # 保存包信息
        save_json(file_path=packages_metainfo_path, data=package_to_file_path)
        logger.info(f"packages metainfo saved to {packages_metainfo_path}")

    def resolve_file_imports(self,
                             file_imports_path: str = FILE_IMPORTS_PATH,
                             junit_version_path: str = JUNIT_VERSION_PATH):
        """
        解析文件导入信息并检测JUnit版本

        提取每个文件的导入语句，并自动检测项目中使用的JUnit版本。
        JUnit版本检测对于测试框架兼容性很重要。

        参数：
            file_imports_path (str): 文件导入信息输出路径
            junit_version_path (str): JUnit版本信息输出路径

        返回：
            Dict[str, List[str]]: 文件路径到导入列表的映射

        JUnit版本检测逻辑：
            1. JUnit 5: 包含 "import org.junit.jupiter.api.Test;"
            2. JUnit 4: 包含 "import org.junit.Test;"
        """
        file_imports = {}
        junit_version = None

        # 遍历所有文件的元数据
        for file in self.metainfo:
            # 检测JUnit版本（只在第一次检测到JUnit时设置）
            if junit_version is None:
                contexts = file['contexts']  # 导入语句列表

                if (
                        "import org.junit.jupiter.api.Test;" in contexts or
                        "import org.junit.jupiter.api.*;" in contexts
                ):
                    junit_version = '5'
                    logger.info(f"Detected JUnit version: {junit_version}")
                elif "import org.junit.Test;" in contexts:
                    junit_version = '4'
                    logger.info(f"Detected JUnit version: {junit_version}")

            # 构建文件导入映射
            file_imports[file['relative_path']] = file['contexts']

        # 检查是否检测到JUnit版本
        if junit_version is None:
            logger.error("JUnit version not detected.")
            raise Exception("JUnit version not detected.")

        # 保存文件导入信息
        save_json(file_imports_path, file_imports)
        logger.info(f"Saved file imports to {file_imports_path}")

        # 保存JUnit版本信息
        save_json(junit_version_path, {"junit_version": junit_version})
        logger.info(f"Saved JUnit version to {junit_version_path}")

        return file_imports

    def get_standard_method_name(self, method: Method) -> str:
        """
        生成标准化的方法名称字符串

        格式：[返回类型]方法名(参数类型1,参数类型2,...)
        用于方法的唯一标识和显示。

        参数：
            method (Method): 方法对象

        返回：
            str: 标准化方法名称

        示例：
            输入：方法名为"getUser"，返回类型"User"，参数类型["int"]
            输出："[User]getUser(int)"
        """
        # 提取参数类型列表
        param_types = [param['type'] for param in method.params]
        # 构建标准化名称
        return f'[{method.return_type}]' + method.name + '(' + ','.join(param_types) + ')'

    def is_non_marker_test_method(self, non_marker_annotations: List[str]) -> bool:
        """
        判断是否为非标记注解的测试方法

        有些测试框架可能不使用标准的@Test注解，
        而是使用其他方式标记测试方法。

        参数：
            non_marker_annotations (List[str]): 非标记注解列表

        返回：
            bool: 是否为测试方法
        """
        for marker in non_marker_annotations:
            # 检查是否包含测试相关的标识
            if 'ParameterizedTest' in marker or 'Test' in marker:
                return True
        return False

    def build_metainfo(self):
        """
        构建Java元信息的主要方法

        从原始元数据中提取信息，创建Java特有的对象模型。
        处理普通类、抽象类、接口、记录、测试类等多种类型。

        处理流程：
            1. 遍历所有文件的元数据
            2. 处理每个文件中的类、接口、记录
            3. 识别测试类和测试方法
            4. 创建相应的对象模型
            5. 构建方法URI和标准名称

        注意：
            - 包含调试断点（第78行）
            - 处理内部类的情况
            - 避免重复添加测试类
        """
        # 用于记录已处理的测试类，避免重复
        testclass_set = set()

        # 遍历所有文件的元数据
        for file in self.metainfo:
            file_path = file['relative_path']

            # 调试断点：特定文件调试
            if file_path == "src/main/java/io/github/sashirestela/openai/BaseSimpleOpenAI.java":
                pass  # 调试时在这里设置断点

            # 处理普通类和抽象类
            classes = file['classes']
            for cls in classes:
                is_test_class = False  # 是否为测试类
                is_abstract_class = False  # 是否为抽象类
                inner_class = None  # 内部类信息
                method_list = []  # 普通方法列表
                testcase_list = []  # 测试方法列表

                methods = cls['methods']

                # 检查是否为抽象类
                if 'abstract' in cls.get('attributes', {}).get('non_marker_annotations', []):
                    is_abstract_class = True

                # 获取内部类信息
                inner_class = cls.get('attributes', {}).get('classes', [])
                if inner_class:
                    logger.info(f"Found inner class in {file_path} {cls['name']}")

                # 处理类中的方法
                for method in methods:
                    marker_annotations = method['attributes'].get('marker_annotations', [])
                    non_marker_annotations = method['attributes'].get('non_marker_annotations', [])
                    return_type = method.get('attributes', {}).get('return_type', '')

                    # 生成方法URI（唯一标识符）
                    uri = JavaMethodSignature(
                        file_path=file['relative_path'],
                        class_name=cls['name'],
                        method_name=method['name'],
                        params=method['params'],
                        return_type=return_type
                    ).unique_name()

                    # 判断是否为测试方法
                    is_test_method = (
                            '@Test' in marker_annotations or
                            '@ParameterizedTest' in marker_annotations or
                            self.is_non_marker_test_method(non_marker_annotations)
                    )

                    if is_test_method:
                        # 创建测试方法对象
                        is_test_class = True
                        testcase = TestMethod(
                            uris=uri,
                            name=method['name'],
                            arg_nums=len(method['params']),
                            params=method['params'],
                            signature=method['signature'],
                            original_string=method['original_string'],
                            file=file['relative_path'],
                            attributes=method['attributes'],
                            docstring=method['docstring'],
                            class_name=cls['name'],
                            class_uri=file['relative_path'] + '.' + cls['name'],
                            return_type=return_type
                        )
                        self.testcases.append(testcase)
                        testcase_list.append(testcase)
                    else:
                        # 创建普通方法对象
                        _method = Method(
                            uris=uri,
                            name=method['name'],
                            arg_nums=len(method['params']),
                            params=method['params'],
                            signature=method['signature'],
                            original_string=method['original_string'],
                            file=file['relative_path'],
                            attributes=method['attributes'],
                            docstring=method['docstring'],
                            class_name=cls['name'],
                            class_uri=file['relative_path'] + '.' + cls['name'],
                            return_type=return_type,
                        )
                        self.methods.append(_method)
                        method_list.append(_method)

                # 根据类类型创建相应的类对象
                if is_abstract_class:
                    # 创建抽象类对象
                    _class = JavaAbstractClass(
                        uris=file['relative_path'] + '.' + cls['name'],
                        name=cls['name'],
                        file_path=file_path,
                        superclasses=cls['superclasses'],
                        super_interfaces=cls['super_interfaces'],
                        methods=[self.get_standard_method_name(method) for method in method_list],
                        method_uris=[method.uris for method in method_list],
                        attributes=inner_class,
                        class_docstring=cls['class_docstring'],
                        original_string=cls['original_string'],
                        fields=cls.get('attributes', {}).get('fields', []),
                    )
                    self.abstract_classes.append(_class)

                elif not is_test_class:
                    # 创建普通类对象
                    _class = JavaClass(
                        uris=file['relative_path'] + '.' + cls['name'],
                        name=cls['name'],
                        file_path=file_path,
                        superclasses=cls['superclasses'],
                        super_interfaces=cls['super_interfaces'],
                        methods=[self.get_standard_method_name(method) for method in method_list],
                        method_uris=[method.uris for method in method_list],
                        attributes=inner_class,
                        class_docstring=cls['class_docstring'],
                        original_string=cls['original_string'],
                        fields=cls.get('attributes', {}).get('fields', []),
                    )
                    self.classes.append(_class)

                else:
                    # 创建测试类对象（避免重复）
                    if cls['name'] in testclass_set:
                        continue

                    name = cls['name']
                    _class = JavaClass(
                        uris=file['relative_path'] + '.' + cls['name'],
                        name=name,
                        file_path=file_path,
                        superclasses=cls['superclasses'],
                        super_interfaces=cls['super_interfaces'],
                        methods=[self.get_standard_method_name(testcase) for testcase in testcase_list],
                        method_uris=[method.uris for method in method_list],
                        attributes=inner_class,
                        class_docstring=cls['class_docstring'],
                        original_string=cls['original_string'],
                        fields=cls.get('attributes', {}).get('fields', []),
                    )
                    self.testclasses.append(_class)
                    testclass_set.add(name)  # 记录已处理的测试类

            # 处理记录（record，Java 14+特性）
            for record in file['records']:
                r = JavaRecord(
                    uris=file['relative_path'] + '.' + record['name'],
                    name=record['name'],
                    methods=record['methods'],
                    attributes=record['attributes'],
                    class_docstring=record['class_docstring'],
                    original_string=record['original_string'],
                    fields=record['fields'],
                )
                self.records.append(r)

            # 处理接口
            for interface in file['interfaces']:
                method_list = []
                methods = interface['methods']

                # 处理接口中的方法
                for method in methods:
                    # 生成方法URI（接口方法通常没有实现）
                    _method = Method(
                        uris=file['relative_path'] + '.' + interface['name'] + '.' + get_java_standard_method_name(
                            method_name=method['name'],
                            params=method['params'],
                            return_type=method.get('attributes', {}).get('return_type', '')
                        ),
                        name=method['name'],
                        arg_nums=len(method['params']),
                        params=method['params'],
                        signature=method['signature'],
                        original_string=method['original_string'],
                        file=file['relative_path'],
                        attributes=method['attributes'],
                        docstring=method['docstring'],
                        class_name=interface['name'],
                        class_uri=file['relative_path'] + '.' + interface['name'],
                        return_type=method.get('attributes', {}).get('return_type', ''),
                    )
                    self.methods.append(_method)
                    method_list.append(_method)

                # 创建接口对象
                i = JavaInterface(
                    uris=file['relative_path'] + '.' + interface['name'],
                    name=interface['name'],
                    file_path=file_path,
                    superclasses=interface['extends_interfaces'],
                    methods=[self.get_standard_method_name(method) for method in method_list],
                    method_uris=[method.uris for method in method_list],
                    class_docstring=interface['interface_docstring'],
                    original_string=interface['original_string'],
                    fields=interface.get('attributes', {}).get('fields', []),
                )
                self.interfaces.append(i)