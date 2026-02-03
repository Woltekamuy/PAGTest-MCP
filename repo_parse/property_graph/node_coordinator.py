"""
节点协调器模块

该模块是测试用例与代码元素（类、方法）之间的协调器，负责建立和管理测试覆盖关系。
通过分析测试用例的分析结果，构建测试元素与代码元素之间的映射关系，支持测试增强和代码理解。

主要功能：
1. 构建方法到测试用例的映射关系（主要测试和相关测试）
2. 构建类到测试用例的映射关系（继承方法映射）
3. 获取现有的测试增强关系（兄弟类、父子类、接口兄弟）
4. 支持基于继承关系的测试用例复用分析

核心类：
- NodeCoordinator: 节点协调器基类
- JavaNodeCoordinator: Java语言特定的节点协调器

数据流：
    测试用例分析结果 → 方法-测试用例映射 → 类-测试用例映射 → 测试增强关系

关键映射：
    1. method_to_primary_testcase: 方法到主要测试用例的映射
    2. method_to_relevant_testcase: 方法到相关测试用例的映射
    3. class_to_primary_testcase: 类到主要测试用例的映射
    4. class_to_relevant_testcase: 类到相关测试用例的映射

增强类型：
    1. Brother Enhancements: 兄弟类之间的测试用例复用
    2. Parent/Child Enhancements: 父子类之间的测试用例复用
    3. Interface Brother Enhancements: 接口实现类之间的测试用例复用

"""

from collections import defaultdict
from typing import Dict, List, Set

from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.llm.llm import LLM
# from repo_parse.llm.qwen_llm import QwenLLM  # 注释掉的备用LLM
from repo_parse.config import (
    BROTHER_ENHANCEMENTS_PATH,
    CHILD_ENHANCEMENTS_PATH,
    CLASS_PROPERTY_PATH,
    CLASS_TO_PRIMARY_TESTCASE_PATH,
    CLASS_TO_RELEVANT_TESTCASE_PATH,
    FULL_UNMAPPED_NODES_PATH,
    INHERIT_TREE_PATH,
    INTERFACE_BROTHER_ENHANCEMENTS_PATH,
    INTERFACE_BROTHER_RELATIONS_PATH,
    INTERFACE_METAINFO_PATH,
    METHOD_TO_PRIMARY_TESTCASE_PATH,
    METHOD_TO_RELEVANT_TESTCASE_PATH,
    NODE_COORDINATOR_RESULT_PATH,
    NODE_TO_TESTCASE_PATH,
    PACKAGES_METAINFO_PATH,
    PARENT_ENHANCEMENTS_PATH,
    PART_UNMAPPED_NODES_PATH,
    RECORD_METAINFO_PATH,
    TESTCASE_ANALYSIS_RESULT_PATH,
    TESTCLASS_ANALYSIS_RESULT_PATH
)
from repo_parse.context_retrieval.static_retrieval.java_static_context_retrieval import JavaStaticContextRetrieval
from repo_parse.metainfo.inherit_resolver import inherit_resolver
from repo_parse.utils.data_processor import load_json, save_json
from repo_parse import logger


class NodeCoordinator:
    """
    节点协调器基类

    负责协调测试用例与代码元素之间的关系，构建测试覆盖网络。
    提供基础的映射关系和增强分析功能，可被子类特化。

    属性：
        llm (LLM): 语言模型实例，用于高级分析（可选）
        static_context_retrieval: 静态上下文检索器
        testcase_analysis_result (List): 测试用例分析结果
        testclass_analysis_result (List[Dict]): 测试类分析结果
        node_coordinator_result_path (str): 协调器结果保存路径
        node_coordinator_result (List): 协调器分析结果
        part_unmapped_nodes_path (str): 部分未映射节点保存路径
        full_unmapped_nodes_path (str): 完全未映射节点保存路径
        node_to_testcase_path (str): 节点到测试用例映射保存路径
        method_to_primary_testcase_path (str): 方法到主要测试用例映射路径
        method_to_relevant_testcase_path (str): 方法到相关测试用例映射路径
        inherit_resolver (inherit_resolver): 继承关系解析器实例
        class_to_primary_testcase_path (str): 类到主要测试用例映射路径
        class_to_relevant_testcase_path (str): 类到相关测试用例映射路径
    """

    def __init__(
            self,
            llm: LLM = None,
            repo_config=None,
            testcase_analysis_result_path: str = TESTCASE_ANALYSIS_RESULT_PATH,
            testclass_analysis_result_path: str = TESTCLASS_ANALYSIS_RESULT_PATH,
            class_property_path: str = CLASS_PROPERTY_PATH,
            node_coordinator_result_path: str = NODE_COORDINATOR_RESULT_PATH,
            part_unmapped_nodes_path: str = PART_UNMAPPED_NODES_PATH,
            full_unmapped_nodes_path: str = FULL_UNMAPPED_NODES_PATH,
            node_to_testcase_path: str = NODE_TO_TESTCASE_PATH,
            static_context_retrieval=None,
            method_to_primary_testcase_path: str = METHOD_TO_PRIMARY_TESTCASE_PATH,
            method_to_relevant_testcase_path: str = METHOD_TO_RELEVANT_TESTCASE_PATH,
    ):
        """
        初始化节点协调器

        参数：
            llm: 语言模型实例，用于高级分析（可选）
            repo_config: 仓库配置对象
            testcase_analysis_result_path: 测试用例分析结果文件路径
            testclass_analysis_result_path: 测试类分析结果文件路径
            class_property_path: 类属性文件路径
            node_coordinator_result_path: 协调器结果保存路径
            part_unmapped_nodes_path: 部分未映射节点保存路径
            full_unmapped_nodes_path: 完全未映射节点保存路径
            node_to_testcase_path: 节点到测试用例映射保存路径
            static_context_retrieval: 静态上下文检索器实例
            method_to_primary_testcase_path: 方法到主要测试用例映射路径
            method_to_relevant_testcase_path: 方法到相关测试用例映射路径
        """
        self.llm = llm
        self.static_context_retrieval = static_context_retrieval
        self.testcase_analysis_result = []
        self.testclass_analysis_result: List[Dict] = load_json(testclass_analysis_result_path)
        self.node_coordinator_result_path = node_coordinator_result_path
        self.node_coordinator_result = []
        self.part_unmapped_nodes_path = part_unmapped_nodes_path
        self.full_unmapped_nodes_path = full_unmapped_nodes_path
        self.node_to_testcase_path = node_to_testcase_path
        self.method_to_primary_testcase_path = method_to_primary_testcase_path
        self.method_to_relevant_testcase_path = method_to_relevant_testcase_path
        self.inherit_resolver = inherit_resolver(repo_config=repo_config)

        # 配置路径（优先使用repo_config）
        if repo_config is not None:
            self.class_to_primary_testcase_path = repo_config.CLASS_TO_PRIMARY_TESTCASE_PATH
            self.class_to_relevant_testcase_path = repo_config.CLASS_TO_RELEVANT_TESTCASE_PATH
        else:
            self.class_to_primary_testcase_path = CLASS_TO_PRIMARY_TESTCASE_PATH
            self.class_to_relevant_testcase_path = CLASS_TO_RELEVANT_TESTCASE_PATH

    def excute(self):
        """
        执行节点协调流程（抽象方法）

        子类需要实现具体的协调逻辑
        """
        pass

    def get_exsiting_brother_having_testcase(
            self,
            inherit_tree_path: str = INHERIT_TREE_PATH,
            brother_enhancements_path: str = BROTHER_ENHANCEMENTS_PATH
    ):
        """
        获取已有测试用例的兄弟类增强关系

        分析兄弟类之间的测试用例复用可能性，为缺少测试的兄弟类
        推荐已有兄弟类的相关测试用例。

        参数：
            inherit_tree_path: 继承树数据文件路径
            brother_enhancements_path: 兄弟增强关系保存路径

        处理逻辑：
            1. 加载类到主要测试用例的映射
            2. 加载继承树中的兄弟关系
            3. 对于每个有测试用例的类，查找其兄弟类
            4. 提取兄弟类与当前类共有的方法
            5. 收集这些方法的测试用例作为增强推荐
        """
        # 加载类到测试用例的映射数据
        data = load_json(self.class_to_primary_testcase_path)
        classes_with_tests = data.keys()  # 已有测试用例的类集合

        # 加载继承树和兄弟关系
        inherit_tree = load_json(inherit_tree_path)
        brother_relations = inherit_tree['brother_relations']  # 兄弟关系映射

        res = defaultdict(list)  # 结果字典：兄弟类 -> 增强信息列表

        # 遍历兄弟关系
        for current_class, brothers in brother_relations.items():
            # 只处理已有测试用例的类
            if current_class in classes_with_tests:
                for brother in brothers:
                    # 获取兄弟类与当前类共有的方法
                    common_methods = self.get_common_methods(child=brother)
                    if common_methods is None:
                        continue

                    # 构建增强信息
                    temp_dict = {
                        "methods": [],  # 测试用例列表
                        "class": current_class,  # 提供测试用例的源类
                    }

                    # 获取当前类的测试用例
                    testcases = data[current_class]
                    method_names = set()  # 用于去重

                    # 处理共有方法签名（去除返回类型等前缀）
                    pruned_methods = [method.split(']')[-1] for method in common_methods]

                    # 筛选与共有方法相关的测试用例
                    for testcase in testcases:
                        if testcase['method_name'] in pruned_methods:
                            if testcase['method_name'] not in method_names:
                                method_names.add(testcase['method_name'])
                                temp_dict['methods'].append(testcase)

                    # 如果找到相关测试用例，添加到结果
                    if temp_dict['methods']:
                        res[brother].append(temp_dict)

        # 保存兄弟增强关系
        save_json(file_path=brother_enhancements_path, data=res)
        logger.info(f'Brother enhancements saved to {brother_enhancements_path}')

    def get_exsiting_parent_child_having_testcase(
            self,
            inherit_tree_path: str = INHERIT_TREE_PATH,
            parent_enhancements_path: str = PARENT_ENHANCEMENTS_PATH,
            child_enhancements_path: str = CHILD_ENHANCEMENTS_PATH
    ):
        """
        获取已有测试用例的父子类增强关系

        分析父子类之间的测试用例复用可能性，支持两个方向：
        1. 子类复用父类的测试用例（子类增强）
        2. 父类复用子类的测试用例（父类增强）

        参数：
            inherit_tree_path: 继承树数据文件路径
            parent_enhancements_path: 父类增强关系保存路径
            child_enhancements_path: 子类增强关系保存路径
        """
        # 加载类到测试用例的映射数据
        data = load_json(self.class_to_primary_testcase_path)
        classes_with_tests = data.keys()  # 已有测试用例的类集合

        # 加载继承树和父子关系
        inherit_tree = load_json(inherit_tree_path)
        child_to_parent = inherit_tree.get('parents', {})  # 子类 -> 父类映射

        parent_enhancements = defaultdict(list)  # 父类增强：子类 -> 父类的测试用例
        child_enhancements = defaultdict(list)  # 子类增强：父类 -> 子类的测试用例

        # 遍历父子关系
        for child, parent in child_to_parent.items():
            # 方向1：父类有测试用例，子类可复用
            if parent in classes_with_tests:
                common_methods = self.get_common_methods(child=child)
                if common_methods is None:
                    continue

                temp_dict = {
                    "methods": [],
                    "class": parent,  # 提供测试用例的父类
                }

                testcases = data[parent]
                method_names = set()
                pruned_methods = [method.split(']')[-1] for method in common_methods]

                for testcase in testcases:
                    if testcase['method_name'] in pruned_methods:
                        if testcase['method_name'] not in method_names:
                            method_names.add(testcase['method_name'])
                            temp_dict['methods'].append(testcase)

                if temp_dict['methods']:
                    parent_enhancements[child].append(temp_dict)

            # 方向2：子类有测试用例，父类可复用
            if child in classes_with_tests:
                common_methods = self.get_common_methods(child=child)
                if common_methods is None:
                    continue

                temp_dict = {
                    "methods": [],
                    "class": child,  # 提供测试用例的子类
                }

                testcases = data[child]
                method_names = set()
                pruned_methods = [method.split(']')[-1] for method in common_methods]

                for testcase in testcases:
                    if testcase['method_name'] in pruned_methods:
                        if testcase['method_name'] not in method_names:
                            method_names.add(testcase['method_name'])
                            temp_dict['methods'].append(testcase)

                if temp_dict['methods']:
                    child_enhancements[parent].append(temp_dict)

        # 保存增强关系
        save_json(file_path=parent_enhancements_path, data=parent_enhancements)
        save_json(file_path=child_enhancements_path, data=child_enhancements)
        logger.info(f'Parent enhancements saved to {parent_enhancements_path}')
        logger.info(f'Child enhancements saved to {child_enhancements_path}')

    def get_exsiting_interface_brother_having_testcase(
            self,
            interface_brother_relations_path: str = INTERFACE_BROTHER_RELATIONS_PATH,
            interface_brother_enhancements_path: str = INTERFACE_BROTHER_ENHANCEMENTS_PATH
    ):
        """
        获取已有测试用例的接口兄弟类增强关系

        分析实现同一接口的类之间的测试用例复用可能性。

        参数：
            interface_brother_relations_path: 接口兄弟关系文件路径
            interface_brother_enhancements_path: 接口兄弟增强关系保存路径

        注意：
            接口兄弟指的是实现同一接口的不同类，它们应该实现相同的方法签名。
        """
        # 加载类到测试用例的映射数据
        data = load_json(self.class_to_primary_testcase_path)
        classes_with_tests = data.keys()  # 已有测试用例的类集合

        # 加载接口兄弟关系
        interface_brother_relations = load_json(interface_brother_relations_path)
        res = defaultdict(list)  # 结果字典：兄弟类 -> 增强信息列表

        # 遍历接口兄弟关系
        for item in interface_brother_relations:
            implementations = item['implementations']  # 实现该接口的类URI列表
            interface_methods = item['methods']  # 接口定义的所有方法

            for implementation in implementations:
                # 提取简单类名（去除包路径）
                simple_class_name = implementation.split('.')[-1]

                # 只处理已有测试用例的类
                if simple_class_name in classes_with_tests:
                    for brother in implementations:
                        if brother == implementation:
                            continue  # 跳过自身

                        # 构建增强信息
                        temp_dict = {
                            "methods": [],  # 测试用例列表
                            "interface_brother": implementation,  # 提供测试用例的源类
                        }

                        # 获取源类的测试用例
                        testcases = data[simple_class_name]
                        method_names = set()  # 用于去重

                        # 处理接口方法签名
                        pruned_methods = [method.split(']')[-1] for method in interface_methods]

                        # 筛选与接口方法相关的测试用例
                        for testcase in testcases:
                            if testcase['method_name'] in pruned_methods:
                                if testcase['method_name'] not in method_names:
                                    method_names.add(testcase['method_name'])
                                    temp_dict['methods'].append(testcase)

                        # 如果找到相关测试用例，添加到结果
                        if temp_dict['methods']:
                            brother_simple_name = brother.split('.')[-1]
                            res[brother_simple_name].append(temp_dict)

        # 保存接口兄弟增强关系
        save_json(file_path=interface_brother_enhancements_path, data=res)
        logger.info(f'Interface brother enhancements saved to {interface_brother_enhancements_path}')

    def get_testcase_analysis_result(self, file_path: str, testcase_name: str) -> Dict:
        """
        根据文件路径和测试用例名称获取测试用例分析结果

        参数：
            file_path: 测试用例文件路径
            testcase_name: 测试用例名称

        返回：
            Dict: 测试用例分析结果字典

        异常：
            如果找不到对应的测试用例分析结果，抛出异常
        """
        for testcase in self.testcase_analysis_result:
            if testcase['test_case_name'] == testcase_name and testcase['file'] == file_path:
                return testcase
        logger.exception(f"testcase analysis result of {testcase_name} in file {file_path} can not be found!")
        raise Exception(f"testcase analysis result of {testcase_name} in file {file_path} can not be found!")

    def get_class_property(self, class_name: str) -> Dict:
        """
        根据类名获取类属性

        参数：
            class_name: 类名

        返回：
            Dict: 类属性字典
        """
        for _class in self.class_property:
            if _class['class_name'] == class_name:
                return _class

    def get_tested_class(self, file_path: str) -> List[str]:
        """
        根据测试文件路径获取被测试的类列表

        参数：
            file_path: 测试类文件路径

        返回：
            List[str]: 被测试的类名列表

        逻辑：
            1. 查找对应文件的测试类分析结果
            2. 提取测试用例中'tested'字段的被测类信息
            3. 去重并返回简单类名列表
        """
        for testclass in self.testclass_analysis_result:
            # 匹配文件路径和类名
            if testclass['file_path'] != file_path or testclass['testclass_name'] != testclass['name']:
                continue

            tested_classes = set()
            test_cases = testclass['test_cases']

            # 遍历测试用例，收集被测类
            for testcase in test_cases:
                tested_list = testcase['tested']
                for item in tested_list:
                    # 提取简单类名（去除方法名部分）
                    tested_class_name = item.split('.')[0] if '.' in item else item
                    tested_classes.add(tested_class_name)

            return list(tested_classes)

    def map_method_to_testcase(self, testclass_analysis_result: List[Dict], save: bool = True):
        """
        构建方法到测试用例的映射关系

        从测试类分析结果中提取方法-测试用例关系，构建两个映射：
        1. method_to_primary_testcase: 方法到主要测试用例的映射
        2. method_to_relevant_testcases: 方法到相关测试用例的映射

        参数：
            testclass_analysis_result: 测试类分析结果列表
            save: 是否保存映射结果到文件，默认为True
        """
        method_to_primary_testcase = {}  # 主要测试用例映射
        method_to_relevant_testcases = {}  # 相关测试用例映射

        for testclass_info in testclass_analysis_result:
            if 'test_cases' not in testclass_info:
                logger.error(f"test_cases not found in testclass_info: {testclass_info}")
                continue

            testclass_name = testclass_info['testclass_name']

            for testcase in testclass_info['test_cases']:
                testcase_name = testcase['name']

                # 处理主要测试的方法
                primary_tested = testcase.get('primary_tested', [])
                for tested in primary_tested:
                    # 提取方法签名（最后一部分）
                    method_signature = tested.split('.')[-1] if '.' in tested else tested
                    method_signature = method_signature.replace(' ', '')  # 去除空格

                    if method_signature not in method_to_primary_testcase:
                        method_to_primary_testcase[method_signature] = []

                    method_to_primary_testcase[method_signature].append({
                        'class_name': tested.split('.')[0] if '.' in tested else tested,
                        'file_path': testclass_info['file_path'],
                        'testclass_name': testclass_name,
                        'testcase_name': testcase_name
                    })

                # 处理相关测试的方法
                associated_methods = testcase.get('associated_methods', [])
                for method in associated_methods:
                    method_signature = method.split('.')[-1] if '.' in method else method

                    if method_signature not in method_to_relevant_testcases:
                        method_to_relevant_testcases[method_signature] = []

                    method_to_relevant_testcases[method_signature].append({
                        'class_name': method.split('.')[0] if '.' in method else method,
                        'file_path': testclass_info['file_path'],
                        'testclass_name': testclass_name,
                        'testcase_name': testcase_name
                    })

        if save:
            save_json(file_path=self.method_to_primary_testcase_path, data=method_to_primary_testcase)
            save_json(file_path=self.method_to_relevant_testcase_path, data=method_to_relevant_testcases)
            logger.info("Saving method_to_primary_testcase and method_to_relevant_testcase")

    def map_class_to_testcase(self):
        """
        构建类到测试用例的映射关系

        基于方法到测试用例的映射，聚合生成类级别的测试覆盖关系：
        1. class_to_primary_testcase: 类到主要测试用例的映射
        2. class_to_relevant_testcase: 类到相关测试用例的映射
        """
        logger.info("Mapping class to testcase")

        # 加载方法级别的映射
        method_to_primary_testcase = load_json(self.method_to_primary_testcase_path)
        method_to_relevant_testcase = load_json(self.method_to_relevant_testcase_path)

        # 构建类到主要测试用例的映射
        class_to_primary_testcase = defaultdict(list)
        for method, details_list in method_to_primary_testcase.items():
            for details in details_list:
                class_name = details["class_name"]
                class_to_primary_testcase[class_name].append({
                    "method_name": method,
                    "file_path": details["file_path"],
                    "testclass_name": details["testclass_name"],
                    "testcase_name": details["testcase_name"]
                })

        # 构建类到相关测试用例的映射
        class_to_relevant_testcase = defaultdict(list)
        for method, details_list in method_to_relevant_testcase.items():
            for details in details_list:
                class_name = details["class_name"]
                class_to_relevant_testcase[class_name].append({
                    "method_name": method,
                    "file_path": details["file_path"],
                    "testclass_name": details["testclass_name"],
                    "testcase_name": details["testcase_name"]
                })

        # 保存映射结果
        save_json(file_path=self.class_to_primary_testcase_path, data=class_to_primary_testcase)
        save_json(file_path=self.class_to_relevant_testcase_path, data=class_to_relevant_testcase)
        logger.info("Mapping class to testcase finished")

    def solove_exsisting_enhencement(self, full_unmapped_nodes, save: bool = True):
        """
        解决现有的增强关系（抽象方法）

        参数：
            full_unmapped_nodes: 完全未映射的节点列表
            save: 是否保存结果

        注意：
            子类需要实现具体的增强解决逻辑
        """
        raise NotImplementedError


class JavaNodeCoordinator(NodeCoordinator):
    """
    Java语言特定的节点协调器

    继承自NodeCoordinator，提供Java语言特有的静态上下文检索功能。
    """

    def __init__(
            self,
            llm: LLM = None,
            repo_config=None,
            record_metainfo_path: str = RECORD_METAINFO_PATH,
            interface_metainfo_path: str = INTERFACE_METAINFO_PATH,
            packages_metainfo_path: str = PACKAGES_METAINFO_PATH,
            testcase_analysis_result_path: str = TESTCASE_ANALYSIS_RESULT_PATH,
            testclass_analysis_result_path: str = TESTCLASS_ANALYSIS_RESULT_PATH,
            class_property_path: str = CLASS_PROPERTY_PATH,
            node_coordinator_result_path: str = NODE_COORDINATOR_RESULT_PATH,
            part_unmapped_nodes_path: str = PART_UNMAPPED_NODES_PATH,
            full_unmapped_nodes_path: str = FULL_UNMAPPED_NODES_PATH,
            node_to_testcase_path: str = NODE_TO_TESTCASE_PATH,
            method_to_primary_testcase_path: str = METHOD_TO_PRIMARY_TESTCASE_PATH,
            method_to_relevant_testcase_path: str = METHOD_TO_RELEVANT_TESTCASE_PATH,
    ):
        """
        初始化Java节点协调器

        参数：
            llm: 语言模型实例
            repo_config: 仓库配置对象
            record_metainfo_path: 记录类型元信息文件路径
            interface_metainfo_path: 接口元信息文件路径
            packages_metainfo_path: 包元信息文件路径
            testcase_analysis_result_path: 测试用例分析结果文件路径
            testclass_analysis_result_path: 测试类分析结果文件路径
            class_property_path: 类属性文件路径
            node_coordinator_result_path: 协调器结果保存路径
            part_unmapped_nodes_path: 部分未映射节点保存路径
            full_unmapped_nodes_path: 完全未映射节点保存路径
            node_to_testcase_path: 节点到测试用例映射保存路径
            method_to_primary_testcase_path: 方法到主要测试用例映射路径
            method_to_relevant_testcase_path: 方法到相关测试用例映射路径
        """
        # 创建Java静态上下文检索器
        static_context_retrieval = JavaStaticContextRetrieval(
            repo_config=repo_config,
            record_metainfo_path=record_metainfo_path,
            interface_metainfo_path=interface_metainfo_path,
            packages_metainfo_path=packages_metainfo_path
        )

        # 调用父类初始化
        super().__init__(
            llm,
            repo_config=repo_config,
            testcase_analysis_result_path=testcase_analysis_result_path,
            testclass_analysis_result_path=testclass_analysis_result_path,
            static_context_retrieval=static_context_retrieval,
            class_property_path=class_property_path,
            node_coordinator_result_path=node_coordinator_result_path,
            part_unmapped_nodes_path=part_unmapped_nodes_path,
            full_unmapped_nodes_path=full_unmapped_nodes_path,
            node_to_testcase_path=node_to_testcase_path,
            method_to_primary_testcase_path=method_to_primary_testcase_path,
            method_to_relevant_testcase_path=method_to_relevant_testcase_path,
        )


def run_node_coordinator(coordinator: NodeCoordinator):
    """
    运行节点协调器的主要流程

    参数：
        coordinator: 节点协调器实例或可调用对象

    执行流程：
        1. 加载测试类分析结果
        2. 构建方法到测试用例的映射
        3. 构建类到测试用例的映射
        4. 分析各种增强关系（兄弟类、父子类、接口兄弟）
    """
    logger.info("Node Coordinator Start!")

    # 实例化协调器（如果传入的是类而不是实例）
    if callable(coordinator):
        coordinator = coordinator()

    # 加载测试类分析结果
    testclass_analysis_result = load_json(TESTCLASS_ANALYSIS_RESULT_PATH)

    # 执行协调器主要流程
    coordinator.map_method_to_testcase(testclass_analysis_result)
    coordinator.map_class_to_testcase()
    coordinator.get_exsiting_brother_having_testcase()
    coordinator.get_exsiting_parent_child_having_testcase()
    coordinator.get_exsiting_interface_brother_having_testcase()

    logger.info("Node Coordinator Done!")