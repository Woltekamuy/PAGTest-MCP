"""

核心类：
- MetaInfo: 元信息管理主类，提供所有元信息的查询和操作方法
- run_build_metainfo: 元信息构建入口函数
"""

from typing import List

from repo_parse.metainfo.interface_resolver import InterfaceResolver
from repo_parse.metainfo.java_metainfo_builder import JavaMetaInfoBuilder
from repo_parse.metainfo.metainfo_builder import MetaInfoBuilder
from repo_parse.metainfo.potential_brother_resolver import PotentialBrotherResolver
from repo_parse.parser.tree_sitter_query_parser import extract_identifiers
from repo_parse.utils.data_processor import load_class_metainfo, load_file_imports_metainfo, load_json, load_method_metainfo, load_packages_metainfo, load_testcase_metainfo
from repo_parse import config
from repo_parse import logger


class MetaInfo:
    """
    元信息管理类

    负责加载、管理和查询代码仓库的元数据信息，包括：
    - 类信息（普通类、测试类、抽象类）
    - 方法信息
    - 测试用例信息
    - 接口信息
    - 包信息
    - 文件导入信息

    属性：
        class_metainfo_path (str): 类元信息文件路径
        method_metainfo_path (str): 方法元信息文件路径
        testcase_metainfo_path (str): 测试用例元信息文件路径
        testclass_metainfo_path (str): 测试类元信息文件路径
        packages_metainfo_path (str): 包元信息文件路径
        file_imports_metainfo_path (str): 文件导入元信息路径
        abstractclass_metainfo_path (str): 抽象类元信息文件路径
        interface_metainfo_path (str): 接口元信息文件路径
        language_mode (str): 语言模式，默认为"java"

        class_metainfo (list): 加载的类元信息列表
        method_metainfo (list): 加载的方法元信息列表
        testcase_metainfo (list): 加载的测试用例元信息列表
        testclass_metainfo (list): 加载的测试类元信息列表
        file_imports_metainfo (dict): 加载的文件导入元信息字典
        abstractclass_metainfo (list): 加载的抽象类元信息列表
        interface_metainfo (list): 加载的接口元信息列表
    """

    # 类级常量，存储默认的文件路径配置
    class_metainfo_path = config.CLASS_METAINFO_PATH
    method_metainfo_path = config.METHOD_METAINFO_PATH
    testcase_metainfo_path = config.TESTCASE_METAINFO_PATH
    testclass_metainfo_path = config.TESTCLASS_METAINFO_PATH
    packages_metainfo_path = config.PACKAGES_METAINFO_PATH
    file_imports_metainfo_path = config.FILE_IMPORTS_PATH
    abstractclass_metainfo_path = config.ABSTRACTCLASS_METAINFO_PATH
    interface_metainfo_path = config.INTERFACE_METAINFO_PATH
    language_mode = config.LANGUAGE_MODE

    def __init__(
            self,
            repo_config=None,
            language_mode: str = "java"
    ) -> None:
        """
        初始化MetaInfo实例

        参数：
            repo_config: 仓库配置对象，包含元信息文件路径配置
            language_mode: 语言模式，默认为"java"

        功能：
            1. 如果提供了repo_config，则使用其配置路径
            2. 加载所有类型的元信息到内存中
            3. 设置语言模式
        """
        # 使用自定义配置覆盖默认配置
        if repo_config is not None:
            self.class_metainfo_path = repo_config.CLASS_METAINFO_PATH
            self.method_metainfo_path = repo_config.METHOD_METAINFO_PATH
            self.testcase_metainfo_path = repo_config.TESTCASE_METAINFO_PATH
            self.testclass_metainfo_path = repo_config.TESTCLASS_METAINFO_PATH
            self.packages_metainfo_path = repo_config.PACKAGES_METAINFO_PATH
            self.file_imports_metainfo_path = repo_config.FILE_IMPORTS_PATH
            self.abstractclass_metainfo_path = repo_config.ABSTRACTCLASS_METAINFO_PATH
            self.interface_metainfo_path = repo_config.INTERFACE_METAINFO_PATH

        self.language_mode = language_mode

        # 加载所有元信息数据到内存
        self.class_metainfo = load_class_metainfo(self.class_metainfo_path)
        self.method_metainfo = load_method_metainfo(self.method_metainfo_path)
        self.testcase_metainfo = load_testcase_metainfo(self.testcase_metainfo_path)
        self.testclass_metainfo = load_class_metainfo(self.testclass_metainfo_path)
        self.file_imports_metainfo = load_file_imports_metainfo(self.file_imports_metainfo_path)

        self.abstractclass_metainfo = load_json(self.abstractclass_metainfo_path)
        self.interface_metainfo = load_json(self.interface_metainfo_path)

    def get_method(self, uri):
        """
        根据URI精确查找方法

        参数：
            uri: 方法的唯一标识符

        返回：
            dict: 方法元信息字典，如果未找到返回None
        """
        for method in self.method_metainfo:
            if uri == method["uris"]:
                return method

    def get_class(self, uri):
        """
        根据URI精确查找类

        参数：
            uri: 类的唯一标识符

        返回：
            dict: 类元信息字典，如果未找到返回None
        """
        for cls in self.class_metainfo:
            if uri == cls["uris"]:
                return cls

    def get_interface(self, uri):
        """
        根据URI精确查找接口

        参数：
            uri: 接口的唯一标识符

        返回：
            dict: 接口元信息字典，如果未找到返回None
        """
        for cls in self.interface_metainfo:
            if uri == cls["uris"]:
                logger.info(f"Found interface {cls['name']}")
                return cls

    def get_abstractclass(self, uri):
        """
        根据URI精确查找抽象类

        参数：
            uri: 抽象类的唯一标识符

        返回：
            dict: 抽象类元信息字典，如果未找到返回None
        """
        for cls in self.abstractclass_metainfo:
            if uri == cls["uris"]:
                logger.info(f"Found abstract class {cls['name']}")
                return cls

    def get_imports(self, file_path) -> List[str]:
        """
        获取指定文件的导入语句列表

        参数：
            file_path: 文件路径

        返回：
            List[str]: 导入语句列表，如果未找到返回空列表
        """
        return self.file_imports_metainfo.get(file_path, [])

    def get_testcase(self, uri):
        """
        根据URI精确查找测试用例

        参数：
            uri: 测试用例的唯一标识符

        返回：
            dict: 测试用例元信息字典，如果未找到返回None
        """
        for testcase in self.testcase_metainfo:
            if testcase["uris"] == uri:
                return testcase

    def get_testclass(self, uri):
        """
        根据URI精确查找测试类

        参数：
            uri: 测试类的唯一标识符

        返回：
            dict: 测试类元信息字典，如果未找到返回None
        """
        for cls in self.testclass_metainfo:
            if uri == cls["uris"]:
                return cls

    def get_interface_montage(self, interface):
        """
        获取接口的概要信息（montage）

        参数：
            interface: 接口元信息字典

        返回：
            dict: 包含接口名称和方法签名的字典
        """
        return {
            "interface_name": interface["name"],
            "methods_signature": [method for method in interface["methods"]]
        }

    def get_abstractclass_montage(self, abstractclass):
        """
        获取抽象类的概要信息（montage）

        参数：
            abstractclass: 抽象类元信息字典

        返回：
            dict: 包含抽象类名称和方法签名的字典
        """
        return {
            "abstract_class_name": abstractclass["name"],
            "methods_signature": [method for method in abstractclass["methods"]]
        }

    def get_class_montage(self, _class, use_doc=False):
        """
        获取类的概要信息（montage）

        参数：
            _class: 类元信息字典
            use_doc: 是否包含文档字符串，默认为False

        返回：
            dict: 包含类名、方法签名和字段信息的字典
                如果use_doc为True，则包含文档信息
        """
        method_uris = _class['method_uris']
        methods_signature = []
        if not use_doc:
            # 不包含文档信息版本
            for method in self.method_metainfo:
                if method["uris"] in method_uris:
                    methods_signature.append(method["signature"])
            return {
                "class_name": _class['name'],
                "methods_signature": methods_signature,
                "fields": [field['attribute_expression'] for field in _class['fields']]
            }
        else:
            # 包含文档信息版本
            for method in self.method_metainfo:
                if method["uris"] in method_uris:
                    methods_signature.append([method["docstring"], method["signature"]])
            return {
                "class_name": _class['name'],
                "class_doc": _class['class_docstring'],
                "methods_signature": methods_signature,
                "fields": [field["docstring"] + field['attribute_expression'] for field in _class['fields']]
            }

    def get_type_or_none(self, type_name, package_name, metadata):
        """
        在指定包中查找指定名称的类型

        参数：
            type_name: 类型名称
            package_name: 包名
            metadata: 要搜索的元数据列表

        返回：
            dict: 找到的类型元信息，如果未找到或存在歧义返回None
        """
        res = []
        for item in metadata:
            if item['name'] == type_name:
                res.append(item)

        # 处理同名类型的情况
        if len(res) > 1:
            logger.warning(f"Found {len(res)} items with the same name {type_name} in package {package_name}")
            for item in res:
                package = item['file_path'].split('.java')[0].split('src/main/java/')[-1].replace('/', '.')
                if package == package_name:
                    logger.info(f"Found the item {item['name']} in package {package}")
                    return item

        return res[0] if len(res) > 0 else None

    def get_class_or_none(self, class_name, package_name):
        """
        在指定包中查找指定名称的类

        参数：
            class_name: 类名
            package_name: 包名

        返回：
            dict: 类元信息，如果未找到返回None
        """
        return self.get_type_or_none(class_name, package_name, self.class_metainfo)

    def get_interface_or_none(self, interface_name, package_name):
        """
        在指定包中查找指定名称的接口

        参数：
            interface_name: 接口名
            package_name: 包名

        返回：
            dict: 接口元信息，如果未找到返回None
        """
        return self.get_type_or_none(interface_name, package_name, self.interface_metainfo)

    def get_abstractclass_or_none(self, abstractclass_name, package_name):
        """
        在指定包中查找指定名称的抽象类

        参数：
            abstractclass_name: 抽象类名
            package_name: 包名

        返回：
            dict: 抽象类元信息，如果未找到返回None
        """
        return self.get_type_or_none(abstractclass_name, package_name, self.abstractclass_metainfo)

    def process_method_and_field_invocations(self, original_string, class_name, file_path, _class):
        """
        处理方法和字段的调用关系

        从原始字符串中提取被调用的方法和字段，并在指定类中查找对应的定义

        参数：
            original_string: 原始代码字符串
            class_name: 类名
            file_path: 文件路径
            _class: 类元信息

        返回：
            tuple: (methods, fields)
                   methods: 找到的方法定义列表
                   fields: 找到的字段定义列表
        """
        methods_invoked, field_invoked = extract_identifiers(original_string=original_string, invoker_name=class_name)
        methods_invoked = [method.strip('.').split('(')[0] for method in methods_invoked]

        methods = []
        fields = []

        # 查找被调用的方法定义
        if methods_invoked:
            for method in self.method_metainfo:
                if file_path == method['file'] and method['name'] in methods_invoked:
                    logger.info(f"Find method {method['name']} in class {class_name}.")
                    methods.append(method['original_string'])

        # 查找被引用的字段定义
        if field_invoked:
            for field in _class['fields']:
                if field['name'].split('=')[0] in field_invoked:
                    logger.info(f"Find field {field['name']} in class {class_name}.")
                    fields.append(field['attribute_expression'])

        return methods, fields

    def fuzzy_get_method(self, file_path, class_name, method_name):
        """
        模糊查找方法

        参数：
            file_path: 文件路径
            class_name: 类名
            method_name: 方法名

        返回：
            dict: 方法元信息，如果未找到返回None
        """
        for method in self.method_metainfo:
            if method['file'] == file_path and method['class_name'] == class_name and method['name'] == method_name:
                return method

    def fuzzy_get_testcase(self, file_path, class_name, testcase_name):
        """
        模糊查找测试用例

        参数：
            file_path: 文件路径
            class_name: 类名
            testcase_name: 测试用例名

        返回：
            dict: 测试用例元信息，如果未找到返回None
        """
        for testcase in self.testcase_metainfo:
            if testcase['file'] == file_path and testcase['class_name'] == class_name and testcase[
                'name'] == testcase_name:
                return testcase

    def fuzzy_get_class(self, class_name):
        """
        模糊查找类

        参数：
            class_name: 类名

        返回：
            dict: 类元信息，如果未找到返回None
        """
        for cls in self.class_metainfo:
            if class_name == cls['name']:
                return cls

    def fuzzy_get_testclass(self, testclass_name):
        """
        模糊查找测试类

        参数：
            testclass_name: 测试类名

        返回：
            dict: 测试类元信息，如果未找到返回None
        """
        for testclass in self.testclass_metainfo:
            if testclass_name == testclass['name']:
                return testclass

    def fuzzy_get_record(self, record_name):
        """
        模糊查找记录类型（record）

        参数：
            record_name: 记录类型名

        返回：
            dict: 记录类型元信息，如果未找到返回None
        """
        for record in self.record_metainfo:
            if record_name == record['name']:
                return record

    def fuzzy_get_interface(self, interface_name):
        """
        模糊查找接口

        参数：
            interface_name: 接口名

        返回：
            dict: 接口元信息，如果未找到返回None
        """
        for interface in self.interface_metainfo:
            if interface_name == interface['name']:
                return interface

    def fuzzy_get_abstractclass(self, abstractclass_name):
        """
        模糊查找抽象类

        参数：
            abstractclass_name: 抽象类名

        返回：
            dict: 抽象类元信息，如果未找到返回None
        """
        for abstractclass in self.abstractclass_metainfo:
            if abstractclass_name == abstractclass['name']:
                return abstractclass

    def get_common_methods(self, child):
        """
        获取子类从父类继承的公共方法

        参数：
            child: 子类名

        返回：
            set: 公共方法集合，如果父类不存在返回None
        """
        child_class = self.fuzzy_get_class(class_name=child)
        if child_class is None:
            return None

        parent_class_name = child_class['superclasses']
        parent_class = self.fuzzy_get_class(class_name=parent_class_name)
        if parent_class is None:
            parent_class = self.fuzzy_get_abstractclass(abstractclass_name=parent_class_name)
        if parent_class is None:
            return None

        methods = set(parent_class['methods'])
        return methods

    def pack_testcases_original_string(self, testcases: List[str]) -> str:
        """
        打包多个测试用例的原始字符串

        参数：
            testcases: 测试用例URI列表

        返回：
            str: 拼接后的测试用例原始字符串
        """
        original_string = ""
        for testcase in testcases:
            testcase = self.get_testcase(testcase)
            if testcase is not None:
                original_string += testcase["original_string"]
                original_string += "\n\n"
        return original_string

    def pack_testclass_and_imports_for_testcases(self, testcase_uris: List[str]) -> str:
        """
        为测试用例打包对应的测试类和导入语句

        参数：
            testcase_uris: 测试用例URI列表

        返回：
            str: 包含导入语句和测试类定义的字符串
        """
        res = ""
        class_uri_set = set()
        for testcase_uri in testcase_uris:
            testcase = self.get_testcase(testcase_uri)
            class_uri = testcase['class_uri']

            # 避免重复添加同一个测试类
            if class_uri in class_uri_set:
                continue

            class_uri_set.add(class_uri)
            file_path = testcase['file']
            imports = self.get_imports(file_path)
            if imports is not None:
                res += "\n" + '\n'.join(imports)

            _class = self.get_testclass(class_uri)
            if _class is not None:
                res += "\n" + _class['original_string']
                logger.info(f"Packing testclass {_class['name']} for testcase: {testcase_uri}")

        return res

    def pack_class_montage_description(self, class_montage):
        """
        将类概要信息打包为XML格式的描述字符串

        参数：
            class_montage: 类概要信息字典

        返回：
            str: XML格式的描述字符串
        """
        return (
                "<class_name>" + class_montage['class_name'] + "</class_name>" +
                "<methods_signature>" + '\n'.join(class_montage['methods_signature']) + "</methods_signature>" +
                "<fields>" + '\n'.join(class_montage['fields']) + "</fields>"
        )

    def pack_interface_montage_description(self, interface_montage):
        """
        将接口概要信息打包为XML格式的描述字符串

        参数：
            interface_montage: 接口概要信息字典

        返回：
            str: XML格式的描述字符串
        """
        return (
                "<interface_name>" + interface_montage['interface_name'] + "</interface_name>" +
                "<methods_signature>" + '\n'.join(interface_montage['methods_signature']) + "</methods_signature>"
        )

    def pack_abstractclass_montage_description(self, abstractclass_montage):
        """
        将抽象类概要信息打包为XML格式的描述字符串

        参数：
            abstractclass_montage: 抽象类概要信息字典

        返回：
            str: XML格式的描述字符串
        """
        return (
                "<abstract_class_name>" + abstractclass_montage['abstract_class_name'] + "</abstract_class_name>" +
                "<methods_signature>" + '\n'.join(abstractclass_montage['methods_signature']) + "</methods_signature>"
        )

    def pack_package_class_montages_description(self, package_class_montages):
        """
        打包多个包中类的概要信息描述

        参数：
            package_class_montages: 包类概要信息列表

        返回：
            str: 打包后的描述字符串
        """
        if not package_class_montages:
            return ""

        description = "\nAnd We provide you with the montage information of the package to help you."
        for package_class_montage in package_class_montages:
            description += self.pack_class_montage_description(package_class_montage)
        return description

    def pack_package_refs_description(self, package_refs):
        """
        打包包级引用信息描述

        参数：
            package_refs: 包引用信息列表

        返回：
            str: 打包后的描述字符串
        """
        if not package_refs:
            return ""

        content = "\nAnd we provide you with the package references to help you."
        description = ""
        for package_ref in package_refs:
            methods_str = '\n'.join(package_ref['methods']) if package_ref['methods'] else ""
            fields_str = '\n'.join(package_ref['fields']) if package_ref['fields'] else ""
            description += (
                    "<ref>\n" + "name:\n" + package_ref['name'] + '\n' + methods_str + '\n' + fields_str + "\n</ref>\n"
            )
        return content + description

    def pack_repo_refs_use_dot_description(self, repo_refs):
        """
        打包仓库级引用信息描述（使用点分隔符格式）

        参数：
            repo_refs: 仓库引用信息列表

        返回：
            str: 打包后的描述字符串
        """
        if not repo_refs:
            return ""
        content = "\nAnd we provide you with the repo references of target method to help you."
        description = ""
        for repo_refs in repo_refs:
            methods_str = '\n'.join(repo_refs['methods']) if repo_refs['methods'] else ""
            fields_str = '\n'.join(repo_refs['fields']) if repo_refs['fields'] else ""
            description += (
                    "<ref>\n" + "name:\n" + repo_refs['name'] + '\n' + methods_str + '\n' + fields_str + "\n</ref>\n"
            )
        return content + description


def run_build_metainfo(builder: MetaInfoBuilder):
    """
    运行元信息构建流程

    这是构建代码仓库元信息的主要入口函数，支持不同语言的构建器。
    对于Java语言，还会进行额外的接口解析、兄弟关系解析和包信息解析。

    参数：
        builder: 元信息构建器实例，必须继承自MetaInfoBuilder

    流程：
        1. 构建基础元信息
        2. 保存元信息到文件
        3. 如果是Java构建器，执行额外的解析步骤：
           - 解析文件导入关系
           - 解析接口兄弟关系
           - 解析潜在兄弟关系
           - 解析包级元信息

    示例：
        builder = JavaMetaInfoBuilder()
        run_build_metainfo(builder)
    """
    logger.info('run_build_metainfo start.')

    # 1. 构建基础元信息
    builder.build_metainfo()
    builder.save()

    # 2. Java语言特有的额外解析
    if isinstance(builder, JavaMetaInfoBuilder):
        logger.info('resolve file imports and package level info for Java start...')
        builder.resolve_file_imports()
        logger.info('resolve file imports and package level info for Java finished.')

        # 加载已构建的元信息用于关系解析
        class_metainfo = load_json(config.CLASS_METAINFO_PATH)
        interface_metainfo = load_json(config.INTERFACE_METAINFO_PATH)

        # 3. 解析接口兄弟关系
        resolver = InterfaceResolver(class_metainfo, interface_metainfo)
        _ = resolver.resolve_interface_brother_relation()
        logger.info('resolve interface brother relation finished.')

        # 4. 解析类兄弟关系
        logger.info('resolve class brother relation finished.')

        # 5. 解析潜在兄弟关系
        resolver = PotentialBrotherResolver(class_metainfo)
        _ = resolver.resolve_potential_brothers(similarity_threshold=1.0)
        logger.info('resolve potential brother relation finished.')

        # 6. 解析包级元信息
        builder.resolve_package_metainfo()

    logger.info('run_build_metainfo Done!')


if __name__ == '__main__':
    """
    模块测试和示例代码

    展示如何使用MetaInfoBuilder构建元信息，并解析文件导入关系。
    注释掉了Python构建器的示例，当前使用Java构建器。
    """

    # 测试数据路径
    metainfo_json_path = r'/home/zhangzhe/APT/repo_parse/python_files_results.json'
    resolved_metainfo_path = r'/home/zhangzhe/APT/repo_parse/'

    # Python构建器示例（已注释）
    # builder = PythonMetaInfoBuilder(
    #     metainfo_json_path=metainfo_json_path,
    #     resolved_metainfo_path=resolved_metainfo_path
    # )

    # 创建Java构建器实例
    builder = JavaMetaInfoBuilder()

    # 单独调用构建器方法进行测试（正常使用应调用run_build_metainfo）
    # builder.build_metainfo()
    # builder.save()
    builder.resolve_file_imports()

    # 使用自定义文件路径解析导入（示例代码）
    # builder.resolve_file_imports(file_imports_path=r'/home/zhangzhe/APT/repo_parse/file_imports.json')

    # 解析包级信息（示例代码）
    # builder.resolve_package_level_info(
    #     packages_metainfo_path=r'/home/zhangzhe/APT/repo_parse/packages_metainfo.json')