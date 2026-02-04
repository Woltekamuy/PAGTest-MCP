"""
本模块用于作为 MCP Server 的核心入口之一，负责：
1. Java 仓库的源码解析与元信息构建
2. 基于属性图与继承关系的测试用例分析
3. 调用大模型（LLM）进行测试用例语义分析与生成
4. 协调已有测试与新生成测试之间的映射关系

"""

### 给MCP Server配置好大模型
"""
首先，本工具作为一个MCP Server，运行的时候需要依赖大模型
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

from repo_parse.analysis.testcase_analyzer import JavaTestcaseAnalyzer
from repo_parse.entrypoint.batch_run_for_project import get_testclass_names
from repo_parse.generator.testcase_generator import JavaTestcaseGenerator
from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.metainfo.interface_resolver import InterfaceResolver
from repo_parse.metainfo.potential_brother_resolver import PotentialBrotherResolver
from repo_parse.property_graph.node_coordinator import JavaNodeCoordinator
from repo_parse.utils.data_processor import load_json
from repo_parse.parser.java_parser import RefineJavaParser
from repo_parse.parser.source_parse import Processer, save_json


class RepoConfig:
    """
    【配置聚合类】

    RepoConfig 用于集中管理整个仓库分析与测试生成流程中
    所有路径、开关参数与中间结果文件位置。

    设计意图：
    - 将“配置”与“逻辑”解耦
    - 避免在各模块中硬编码路径或魔法字符串
    - 便于后续做持久化、序列化或多仓库并行分析
    """

    def __init__(self, repo_path: str, package_prefix: str = "", API_BASE: str = "", API_KEY: str = ""):
        # 确保分析工作目录存在，避免后续写文件时报错
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)

        # ===== LLM 相关配置（运行期注入）=====
        self.API_BASE = API_BASE
        self.API_KEY = API_KEY

        # ===== 语言与仓库基础信息 =====
        self.LANGUAGE_MODE = "java"
        self.REPO_PATH = repo_path
        self.PACKAGE_PREFIX = package_prefix

        # ===== 测试分析流程控制开关 =====
        self.SKIP_IF_NOT_RELEVANT_TESTFILES_FOR_CLASS = False
        self.USE_SPECIFY_CLASS_AND_METHOD = True
        self.USE_METHOD_TO_TEST_PATHS = False
        self.METHOD_TO_TEST_PATHS = []

        # ===== 异常 / 无效测试文件处理 =====
        self.BAD_TESTFILE_ARCHIVE_DIR = str(Path(repo_path) / "bad_testfile_archive")
        self.EXCEPTE_PATH = [
            self.BAD_TESTFILE_ARCHIVE_DIR,
        ]

        # ===== 元信息与中间结果文件路径 =====
        self.ALL_METAINFO_PATH = os.path.join(repo_path, "all_metainfo.json")
        self.RESOLVED_METAINFO_PATH = repo_path
        self.LOG_DIR = os.path.join(repo_path, "logs/")

        self.CLASS_METAINFO_PATH = os.path.join(repo_path, "class_metainfo.json")
        self.METHOD_METAINFO_PATH = os.path.join(repo_path, "method_metainfo.json")
        self.TESTCASE_METAINFO_PATH = os.path.join(repo_path, "testcase_metainfo.json")
        self.TESTCLASS_METAINFO_PATH = os.path.join(repo_path, "testclass_metainfo.json")
        self.FILE_IMPORTS_PATH = os.path.join(repo_path, "file_imports.json")
        self.PACKAGES_METAINFO_PATH = os.path.join(repo_path, "packages_metainfo.json")
        self.FILE_METAINFO_PATH = os.path.join(repo_path, "file_metainfo.json")
        self.TESTFILE_METAINFO_PATH = os.path.join(repo_path, "testfile_metainfo.json")
        self.INTERFACE_METAINFO_PATH = os.path.join(repo_path, "interface_metainfo.json")
        self.RECORD_METAINFO_PATH = os.path.join(repo_path, "record_metainfo.json")
        self.ABSTRACTCLASS_METAINFO_PATH = os.path.join(repo_path, "abstractclass_metainfo.json")
        self.JUNIT_VERSION_PATH = os.path.join(repo_path, "junit_version.json")

        # ===== 属性图 / 关系分析结果 =====
        self.CLASS_PROPERTY_PATH = os.path.join(repo_path, "class_property.json")
        self.CLASS_PROPERTY_DIR = os.path.join(repo_path, "class_property/")
        self.CLASS_SIMILARITY_PATH = os.path.join(repo_path, "class_similarity.json")
        self.TESTCASE_ANALYSIS_RESULT_PATH = os.path.join(repo_path, "testcase_analysis_result.json")
        self.TESTCLASS_ANALYSIS_RESULT_PATH = os.path.join(repo_path, "testclass_analysis_result.json")
        self.TESTCLASS_ANALYSIS_RESULT_DIR = os.path.join(repo_path, "testclass_analysis_result/")
        self.INHERIT_TREE_PATH = os.path.join(repo_path, "inherit_tree.json")
        self.FUNC_RELATION_PATH = os.path.join(repo_path, "func_relation.json")
        self.METHOD_PROPERTY_DIR = os.path.join(repo_path, "method_property/")

        # ===== 兄弟 / 父子 / 接口关系增强 =====
        self.BROTHER_RELATIONS_PATH = os.path.join(repo_path, "brother_relations.json")
        self.BROTHER_ENHANCEMENTS_PATH = os.path.join(repo_path, "brother_enhancements.json")
        self.PARENT_ENHANCEMENTS_PATH = os.path.join(repo_path, "parent_enhancements.json")
        self.CHILD_ENHANCEMENTS_PATH = os.path.join(repo_path, "child_enhancements.json")
        self.POTENTIAL_BROTHER_RELATIONS_PATH = os.path.join(repo_path, "potential_brother_relations.json")
        self.INTERFACE_BROTHER_RELATIONS_PATH = os.path.join(repo_path, "interface_brother_relations.json")
        self.INTERFACE_BROTHER_ENHANCEMENTS_PATH = os.path.join(repo_path, "interface_brother_enhancements.json")

        # ===== 节点与测试用例映射 =====
        self.NODE_TO_TESTCASE_PATH = os.path.join(repo_path, "node_to_testcase.json")
        self.NODE_COORDINATOR_RESULT_PATH = os.path.join(repo_path, "node_coordinator_result.json")
        self.PART_UNMAPPED_NODES_PATH = os.path.join(repo_path, "part_unmapped_nodes.json")
        self.FULL_UNMAPPED_NODES_PATH = os.path.join(repo_path, "full_unmapped_nodes.json")
        self.EXISTING_ENHANCEMENTS_PATH = os.path.join(repo_path, "existing_enhancements.json")

        # ===== 方法 / 类 到测试用例的映射关系 =====
        self.METHOD_TO_PRIMARY_TESTCASE_PATH = os.path.join(repo_path, "method_to_primary_testcase.json")
        self.METHOD_TO_RELEVANT_TESTCASE_PATH = os.path.join(repo_path, "method_to_relevant_testcase.json")
        self.CLASS_TO_PRIMARY_TESTCASE_PATH = os.path.join(repo_path, "class_to_primary_testcase.json")
        self.CLASS_TO_RELEVANT_TESTCASE_PATH = os.path.join(repo_path, "class_to_relevant_testcase.json")
        self.HISTORY_TESTCASE_PATHS_PATH = os.path.join(repo_path, "history_testcase_paths.json")

        # ===== 其他辅助文件 =====
        self.FILE_PATHS_WITH_TWO_DOTS = os.path.join(repo_path, "file_paths_with_two_dots.txt")
        self.PROPERTY_GRAPH_PATH = os.path.join(repo_path, "property_graph.json")
        self.METHOD_COVERAGE_RESULT_PATH = os.path.join(repo_path, "method_coverage_result.json")

        # ===== 测试生成相关 =====
        self.GENERATED_TESTCASES_PATH = os.path.join(repo_path, "generated_testcases.json")
        self.GENERATED_TESTCASES_DIR = os.path.join(repo_path, "generated_testcases/")
        self.COMPLETED_TESTCASES_DIR = os.path.join(repo_path, "completed_testcases/")
        self.RUNNING_STATUS_DIR = os.path.join(repo_path, "running_status/")
        self.FAILED_TESTFILES_PATH = os.path.join(repo_path, "failed_testfiles.json")
        self.GENERATED_TESTFILE_RUNNING_STATUS_PATH = os.path.join(repo_path, "generated_testfile_running_status.json")
        self.GENERATED_TESTCASES_RESULT_PATH = os.path.join(repo_path, "generated_testcases_result.json")

        # ===== 实验与最终结果 =====
        self.TESTFILES_PATH = os.path.join(repo_path, "testfiles.txt")
        self.TARGET_METHODS_PATH = os.path.join(repo_path, "target_methods.txt")
        self.CLASS_ALREADY_HAVED_TESTCASE_PATH = os.path.join(repo_path, "class_already_haved_testcase.txt")
        self.EXPERIMENT_RESULT_PATH = os.path.join(repo_path, "experiment_result.json")
        self.TRY_GENERATED_TESTCASES_PATH = os.path.join(repo_path, "try_generated_testcases.json")
        self.FINAL_RESULT_PATH = os.path.join(repo_path, "final_result.json")
        self.STATUS_DISTRIBUTION_PATH = os.path.join(repo_path, "status_distribution.txt")

        # ===== 重试控制 =====
        self.MAX_RETRY_NUMBER = 2


def load_dotenv_file(dotenv_path: str = ".env"):
    """
    【环境变量加载工具函数】

    从 .env 文件中读取 LLM 相关的运行时配置，
    并对关键变量进行完整性校验，避免在深层逻辑中失败。
    """
    load_dotenv(dotenv_path=dotenv_path)
    API_BASE = os.getenv("API_BASE", "")
    API_KEY = os.getenv("API_KEY", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "")
    if not API_BASE or not API_KEY or not MODEL_NAME:
        return False, "API_BASE, API_KEY or MODEL_NAME is not set in .env file."
    return True, (API_BASE, API_KEY, MODEL_NAME)


def parse(repo_path: str, language: str = "Java"):
    """
    【源码解析入口】

    对指定仓库执行语言级源码解析，生成最原始的结构化元信息，
    该步骤不涉及任何语义推理或 LLM 调用。
    """
    print("start repo parsing...")

    # 使用精化后的 Java Parser 构建 AST / 结构信息
    parser = RefineJavaParser()
    processer = Processer(repo_dir=repo_path, language=language, parser=parser)
    results = processer.batch_process(repo_path)

    # 解析结果统一写入 .PAGTest 目录，作为后续分析的输入
    all_metainfo_path = os.path.join(repo_path, ".PAGTest", "all_metainfo.json")
    save_json(all_metainfo_path, results)
    print("repo parsed successfully!")

def build_metainfo(repo_path: str):
    """
    【元信息构建阶段】

    在 parse 阶段生成的原始 metainfo 基础上，
    构建更高层的语义结构与关系信息，包括：
    - 类 / 方法 / 接口 / 抽象类的结构化信息
    - 文件 import 关系
    - 包级别信息
    - 兄弟类、接口兄弟、潜在兄弟关系

    该阶段不涉及 LLM，仅进行规则与结构推导。
    """
    from repo_parse.metainfo.java_metainfo_builder import JavaMetaInfoBuilder
    print('run_build_metainfo start.')

    # 所有分析与中间结果统一放在 .PAGTest 目录下
    repo_path = os.path.join(repo_path, ".PAGTest")
    config = RepoConfig(repo_path)

    # 基于 all_metainfo.json 构建高层语义元信息

    builder = JavaMetaInfoBuilder(
        metainfo_json_path=config.ALL_METAINFO_PATH,
        resolved_metainfo_path=config.RESOLVED_METAINFO_PATH,
        brother_relations_path=config.BROTHER_RELATIONS_PATH,
    )
    builder.build_metainfo()

    # 将构建好的各类 metainfo 持久化到指定路径
    path_to_data = {
        config.CLASS_METAINFO_PATH: builder.classes,
        config.METHOD_METAINFO_PATH: builder.methods,
        config.TESTCASE_METAINFO_PATH: builder.testcases,
        config.TESTCLASS_METAINFO_PATH: builder.testclasses,
        config.RECORD_METAINFO_PATH: builder.records,
        config.INTERFACE_METAINFO_PATH: builder.interfaces,
        config.ABSTRACTCLASS_METAINFO_PATH: builder.abstract_classes
    }
    builder.save(path_to_data)

    # ===== 文件 import 与 JUnit 版本解析 =====
    print('resolve file imports and package level info for Java start...')
    builder.resolve_file_imports(
        file_imports_path=config.FILE_IMPORTS_PATH,
        junit_version_path=config.JUNIT_VERSION_PATH
    )
    print('resolve file imports and package level info for Java finished.')

    # ===== 接口兄弟关系解析 =====
    print('resolve interface brother relation start...')
    class_metainfo = load_json(config.CLASS_METAINFO_PATH)
    interface_metainfo = load_json(config.INTERFACE_METAINFO_PATH)
    resolver = InterfaceResolver(class_metainfo, interface_metainfo)
    _ = resolver.resolve_interface_brother_relation(
        save=True,
        interface_brother_relations_path=config.INTERFACE_BROTHER_RELATIONS_PATH
    )
    print('resolve interface brother relation finished.')
    print('resolve class brother relation finished.')

    # ===== 潜在兄弟类关系（基于相似度） =====
    print('resolve potential brother relation start...')
    resolver = PotentialBrotherResolver(class_metainfo)
    _ = resolver.resolve_potential_brothers(
        similarity_threshold=1.0,
        potential_brother_relations_path=config.POTENTIAL_BROTHER_RELATIONS_PATH
    )
    print('resolve potential brother relation finished.')

    # ===== 包级别元信息补全 =====
    builder.resolve_package_metainfo(
        file_imports_path=config.FILE_IMPORTS_PATH,
        packages_metainfo_path=config.PACKAGES_METAINFO_PATH
    )

    print('run_build_metainfo Done!')


def analyze_testcases(repo_path: str, is_batch: bool = False, filter_list: List[str] = []):
    """
    【测试用例分析阶段（LLM 参与）】

    该阶段是首次引入大模型的关键步骤，主要用于：
    - 理解测试类 / 测试方法的语义与覆盖意图
    - 建立测试用例与被测代码之间的高层映射
    - 为后续测试生成提供上下文与约束

    支持单次分析与批量分析两种模式。
    入参：
    - repo_path(str): 仓库路径
    - is_batch(bool): 是否批量分析，默认为False
    - filter_list(List[str]): 要分析的测试类文件路径列表，如果为空则分析所有测试类
    返回值：
    - status(str): 分析状态，"success"表示成功，"failure"表示失败
    - error(str): 错误信息，如果分析失败则返回错误信息，否则返回None
    注意：
    这一步骤会调用大模型分析测试用例，因此会消耗一定的时间和资源，请注意花费
    """
    print('run_testcase_analyzer start.')

    # 统一切换到分析工作目录
    repo_path = os.path.join(repo_path, ".PAGTest")

    # ===== 加载并校验 LLM 运行环境 =====
    status, envs = load_dotenv_file()
    if not status:
        return "failure", envs
    API_BASE, API_KEY, MODEL_NAME = envs

    config = RepoConfig(
        repo_path,
    )

    # 初始化大模型客户端（DeepSeek）
    llm = DeepSeekLLM(
        api_key=API_KEY,
        api_base=API_BASE,
        model_name=MODEL_NAME,
    )

    # ===== 测试用例高层语义分析 =====
    analyzer = JavaTestcaseAnalyzer(repo_config=config, llm=llm)

    # 解析历史测试路径，用于避免重复分析或生成
    analyzer.reslove_history_testcase_paths(
        analyzer.testclass_metainfo,
        update=False,
        history_testcase_paths_path=config.HISTORY_TESTCASE_PATHS_PATH
    )

    # 根据是否批量模式选择不同分析策略
    if not is_batch:
        analyzer.high_level_analyze(filter_list=filter_list)
    else:
        analyzer.batch_high_level_analyze(
            filter_list=filter_list,
            testclass_analysis_result_dir=config.TESTCLASS_ANALYSIS_RESULT_DIR
        )

    print("Testcase analyzer finished!")

    # ===== 节点协调器：建立“代码节点 ↔ 测试用例”映射 =====
    coordinator = JavaNodeCoordinator(
        llm=llm,
        repo_config=config,
        record_metainfo_path=config.RECORD_METAINFO_PATH,
        interface_metainfo_path=config.INTERFACE_METAINFO_PATH,
        packages_metainfo_path=config.PACKAGES_METAINFO_PATH,
        testcase_analysis_result_path=config.TESTCASE_ANALYSIS_RESULT_PATH,
        testclass_analysis_result_path=config.TESTCLASS_ANALYSIS_RESULT_PATH,
        class_property_path=config.CLASS_PROPERTY_PATH,
        node_coordinator_result_path=config.NODE_COORDINATOR_RESULT_PATH,
        part_unmapped_nodes_path=config.PART_UNMAPPED_NODES_PATH,
        full_unmapped_nodes_path=config.FULL_UNMAPPED_NODES_PATH,
        node_to_testcase_path=config.NODE_TO_TESTCASE_PATH,
        method_to_primary_testcase_path=config.METHOD_TO_PRIMARY_TESTCASE_PATH,
        method_to_relevant_testcase_path=config.METHOD_TO_RELEVANT_TESTCASE_PATH,
    )

    # 方法级映射
    coordinator.map_method_to_testcase(coordinator.testclass_analysis_result)
    # 类级映射
    coordinator.map_class_to_testcase()

    # ===== 利用继承 / 兄弟 / 接口关系补全已有测试覆盖 =====
    coordinator.get_exsiting_brother_having_testcase(
        inherit_tree_path=config.INHERIT_TREE_PATH,
        brother_enhancements_path=config.BROTHER_ENHANCEMENTS_PATH,
    )
    coordinator.get_exsiting_parent_child_having_testcase(
        inherit_tree_path=config.INHERIT_TREE_PATH,
        parent_enhancements_path=config.PARENT_ENHANCEMENTS_PATH,
        child_enhancements_path=config.CHILD_ENHANCEMENTS_PATH,
    )
    coordinator.get_exsiting_interface_brother_having_testcase(
        interface_brother_relations_path=config.INTERFACE_BROTHER_RELATIONS_PATH,
        interface_brother_enhancements_path=config.INTERFACE_BROTHER_ENHANCEMENTS_PATH,
    )

    print("Run node coordinator finished, start to generate testcase in new round.")

    # ===== 生成后续测试生成所需的目标测试类列表 =====
    get_testclass_names(
        class_to_primary_testcase_path=config.CLASS_TO_PRIMARY_TESTCASE_PATH,
        class_already_haved_testcase_path=config.CLASS_ALREADY_HAVED_TESTCASE_PATH
    )
    print("Run testcase analyzer finished.")
    return "success", None


def genereate_testcases(repo_path: str, target_method: str, target_class: str):
    """
    【测试用例生成阶段（LLM 核心能力）】

    针对指定的目标方法与测试类上下文，
    利用大模型生成新的测试用例代码。

    该阶段依赖前序所有分析结果，
    属于“精确生成”而非全量生成。
    """
    print('generate_testcases start.')
    repo_path = os.path.join(repo_path, ".PAGTest")
    config = RepoConfig(repo_path)

    # ===== 加载并校验 LLM 运行环境 =====
    status, envs = load_dotenv_file()
    if not status:
        return "", "", "failure", envs

    API_BASE, API_KEY, MODEL_NAME = envs

    llm = DeepSeekLLM(
        api_key=API_KEY,
        api_base=API_BASE,
        model_name=MODEL_NAME,
    )

    # ===== 根据 target_method 定位 method_metainfo =====
    data = load_json(config.METHOD_METAINFO_PATH)
    class_name = target_class.split(".")[-1]
    for method in data:
        name = '[' + method['uris'].split('[')[-1]
        if name == target_method and method['class_name'] == class_name:
            print(f"Found method {target_method} in class {class_name}")
            target_method = method

    # 若未成功定位目标方法，则直接失败返回
    if not isinstance(target_method, dict):
        print(f".Failed to find method {target_method} in class {class_name}")
        return "", "", [], f"Failed to find method {target_method} in class {class_name}"

    # ===== 调用测试用例生成器 =====
    generator = JavaTestcaseGenerator(llm=llm, repo_config=config)
    target_method_uri, generated_testclass_name, results, error = generator.refined_generate_testcases(
        method=target_method, save=False)
    return target_method_uri, generated_testclass_name, results, error


if __name__ == "__main__":

    repo_path = r"/home/zhangzhe/PAGTest/workspace/commons-collections"

    # parse(
    #     repo_path=repo_path,
    #     language="Java"
    # )

    # build_metainfo(
    #     repo_path=repo_path
    # )


    # """
    # use filter list to do batch analysis, 具体来说，
    # 只有在filter_list中存在的testclass['file_path']才会被分析，
    # 否则会被跳过。
    # filter_list的格式为txt文件，每行一个testclass['file_path']，形如：
    # src/test/java/net/hydromatic/morel/SatTest.java
    # src/test/java/net/hydromatic/morel/compile/ExtentTest.java
    # 这个文件需要放到os.path.dirname(ALL_METAINFO_PATH)目录下，文件名为file_paths_filter.txt
    # """
    # FILE_PATHS_FILTER = os.path.join(repo_path, "file_paths_filter.txt")
    # if os.path.exists(FILE_PATHS_FILTER):
    #     with open(FILE_PATHS_FILTER, 'r') as f:
    #         filter_list = f.read().splitlines()
    # else:
    #     filter_list = []
    # analyze_testcases(
    #     repo_path=repo_path,
    #     is_batch=True,
    #     filter_list=filter_list,
    # )


    target_class = "ArrayStack"
    target_method = "[int]search(Object)"
    target_method_uri, generated_class_name, results, error = genereate_testcases(
        repo_path=repo_path,
        target_method=target_method,
        target_class=target_class,
    )
    print(target_method_uri, generated_class_name)
    if not error:
        print(results)
    else:
        print(error)