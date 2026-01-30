
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
    def __init__(self, repo_path: str, package_prefix: str = "", API_BASE: str = "", API_KEY: str = ""):
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)
            
        self.API_BASE = API_BASE
        self.API_KEY = API_KEY

        self.LANGUAGE_MODE = "java"
        self.REPO_PATH = repo_path
        self.PACKAGE_PREFIX = package_prefix

        self.SKIP_IF_NOT_RELEVANT_TESTFILES_FOR_CLASS = False
        self.USE_SPECIFY_CLASS_AND_METHOD = True
        self.USE_METHOD_TO_TEST_PATHS = False
        self.METHOD_TO_TEST_PATHS = []

        self.BAD_TESTFILE_ARCHIVE_DIR = str(Path(repo_path) / "bad_testfile_archive")
        self.EXCEPTE_PATH = [
            self.BAD_TESTFILE_ARCHIVE_DIR,
        ]

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

        self.CLASS_PROPERTY_PATH = os.path.join(repo_path, "class_property.json")
        self.CLASS_PROPERTY_DIR = os.path.join(repo_path, "class_property/")
        self.CLASS_SIMILARITY_PATH = os.path.join(repo_path, "class_similarity.json")
        self.TESTCASE_ANALYSIS_RESULT_PATH = os.path.join(repo_path, "testcase_analysis_result.json")
        self.TESTCLASS_ANALYSIS_RESULT_PATH = os.path.join(repo_path, "testclass_analysis_result.json")
        self.TESTCLASS_ANALYSIS_RESULT_DIR = os.path.join(repo_path, "testclass_analysis_result/")
        self.INHERIT_TREE_PATH = os.path.join(repo_path, "inherit_tree.json")
        self.FUNC_RELATION_PATH = os.path.join(repo_path, "func_relation.json")
        self.METHOD_PROPERTY_DIR = os.path.join(repo_path, "method_property/")
        self.BROTHER_RELATIONS_PATH = os.path.join(repo_path, "brother_relations.json")
        self.BROTHER_ENHANCEMENTS_PATH = os.path.join(repo_path, "brother_enhancements.json")
        self.PARENT_ENHANCEMENTS_PATH = os.path.join(repo_path, "parent_enhancements.json")
        self.CHILD_ENHANCEMENTS_PATH = os.path.join(repo_path, "child_enhancements.json")
        self.POTENTIAL_BROTHER_RELATIONS_PATH = os.path.join(repo_path, "potential_brother_relations.json")
        self.INTERFACE_BROTHER_RELATIONS_PATH = os.path.join(repo_path, "interface_brother_relations.json")
        self.INTERFACE_BROTHER_ENHANCEMENTS_PATH = os.path.join(repo_path, "interface_brother_enhancements.json")
        self.NODE_TO_TESTCASE_PATH = os.path.join(repo_path, "node_to_testcase.json")
        self.NODE_COORDINATOR_RESULT_PATH = os.path.join(repo_path, "node_coordinator_result.json")
        self.PART_UNMAPPED_NODES_PATH = os.path.join(repo_path, "part_unmapped_nodes.json")
        self.FULL_UNMAPPED_NODES_PATH = os.path.join(repo_path, "full_unmapped_nodes.json")
        self.EXISTING_ENHANCEMENTS_PATH = os.path.join(repo_path, "existing_enhancements.json")
        self.METHOD_TO_PRIMARY_TESTCASE_PATH = os.path.join(repo_path, "method_to_primary_testcase.json")
        self.METHOD_TO_RELEVANT_TESTCASE_PATH = os.path.join(repo_path, "method_to_relevant_testcase.json")
        self.CLASS_TO_PRIMARY_TESTCASE_PATH = os.path.join(repo_path, "class_to_primary_testcase.json")
        self.CLASS_TO_RELEVANT_TESTCASE_PATH = os.path.join(repo_path, "class_to_relevant_testcase.json")
        self.HISTORY_TESTCASE_PATHS_PATH = os.path.join(repo_path, "history_testcase_paths.json")
        self.FILE_PATHS_WITH_TWO_DOTS = os.path.join(repo_path, "file_paths_with_two_dots.txt")
        self.PROPERTY_GRAPH_PATH = os.path.join(repo_path, "property_graph.json")
        self.METHOD_COVERAGE_RESULT_PATH = os.path.join(repo_path, "method_coverage_result.json")

        self.GENERATED_TESTCASES_PATH = os.path.join(repo_path, "generated_testcases.json")
        self.GENERATED_TESTCASES_DIR = os.path.join(repo_path, "generated_testcases/")
        self.COMPLETED_TESTCASES_DIR = os.path.join(repo_path, "completed_testcases/")
        self.RUNNING_STATUS_DIR = os.path.join(repo_path, "running_status/")
        self.FAILED_TESTFILES_PATH = os.path.join(repo_path, "failed_testfiles.json")
        self.GENERATED_TESTFILE_RUNNING_STATUS_PATH = os.path.join(repo_path, "generated_testfile_running_status.json")
        self.GENERATED_TESTCASES_RESULT_PATH = os.path.join(repo_path, "generated_testcases_result.json")
        self.TESTFILES_PATH = os.path.join(repo_path, "testfiles.txt")
        self.TARGET_METHODS_PATH = os.path.join(repo_path, "target_methods.txt")
        self.CLASS_ALREADY_HAVED_TESTCASE_PATH = os.path.join(repo_path, "class_already_haved_testcase.txt")
        self.EXPERIMENT_RESULT_PATH = os.path.join(repo_path, "experiment_result.json")
        self.TRY_GENERATED_TESTCASES_PATH = os.path.join(repo_path, "try_generated_testcases.json")
        self.FINAL_RESULT_PATH = os.path.join(repo_path, "final_result.json")
        self.STATUS_DISTRIBUTION_PATH = os.path.join(repo_path, "status_distribution.txt")
        self.MAX_RETRY_NUMBER = 2

def load_dotenv_file(dotenv_path: str = ".env"):
    load_dotenv(dotenv_path=dotenv_path)
    API_BASE = os.getenv("API_BASE", "")
    API_KEY = os.getenv("API_KEY", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "")
    if not API_BASE or not API_KEY or not MODEL_NAME:
        return False, "API_BASE, API_KEY or MODEL_NAME is not set in .env file."
    return True, (API_BASE, API_KEY, MODEL_NAME)

def parse(repo_path: str, language: str = "Java"):
    print("start repo parsing...")
    
    parser = RefineJavaParser()
    processer = Processer(repo_dir=repo_path, language=language, parser=parser)
    results = processer.batch_process(repo_path)
    all_metainfo_path = os.path.join(repo_path, ".PAGTest", "all_metainfo.json")
    save_json(all_metainfo_path, results)
    print("repo parsed successfully!")
    
def build_metainfo(repo_path: str):
    from repo_parse.metainfo.java_metainfo_builder import JavaMetaInfoBuilder
    print('run_build_metainfo start.')
        
    repo_path = os.path.join(repo_path, ".PAGTest")
    config = RepoConfig(repo_path)


    builder = JavaMetaInfoBuilder(
        metainfo_json_path=config.ALL_METAINFO_PATH,
        resolved_metainfo_path=config.RESOLVED_METAINFO_PATH,
        brother_relations_path=config.BROTHER_RELATIONS_PATH,
    )
    builder.build_metainfo()

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
    
    print('resolve file imports and package level info for Java start...')
    builder.resolve_file_imports(
        file_imports_path=config.FILE_IMPORTS_PATH,
        junit_version_path=config.JUNIT_VERSION_PATH
    )
    print('resolve file imports and package level info for Java finished.')
    
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
        
    print('resolve potential brother relation start...')
    resolver = PotentialBrotherResolver(class_metainfo)
    _ = resolver.resolve_potential_brothers(
        similarity_threshold=1.0, 
        potential_brother_relations_path=config.POTENTIAL_BROTHER_RELATIONS_PATH
    )
    print('resolve potential brother relation finished.')
    
    builder.resolve_package_metainfo(
        file_imports_path=config.FILE_IMPORTS_PATH,
        packages_metainfo_path=config.PACKAGES_METAINFO_PATH
    )
   
    print('run_build_metainfo Done!')
    
def analyze_testcases(repo_path: str, is_batch: bool = False, filter_list: List[str] = []):
    """
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
    
    repo_path = os.path.join(repo_path, ".PAGTest")
    
    status, envs = load_dotenv_file()
    if not status:
        return "failure", envs
    API_BASE, API_KEY, MODEL_NAME = envs
    
    config = RepoConfig(
        repo_path,
    )
    llm = DeepSeekLLM(
        api_key=API_KEY,
        api_base=API_BASE,
        model_name=MODEL_NAME,
    )

    analyzer = JavaTestcaseAnalyzer(repo_config=config, llm=llm)
    analyzer.reslove_history_testcase_paths(
        analyzer.testclass_metainfo, 
        update=False,
        history_testcase_paths_path=config.HISTORY_TESTCASE_PATHS_PATH
    )
    if not is_batch:
        analyzer.high_level_analyze(filter_list=filter_list)
    else:
        analyzer.batch_high_level_analyze(
            filter_list=filter_list, 
            testclass_analysis_result_dir=config.TESTCLASS_ANALYSIS_RESULT_DIR
        )

    print("Testcase analyzer finished!")

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
    coordinator.map_method_to_testcase(coordinator.testclass_analysis_result)
    coordinator.map_class_to_testcase()
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

    get_testclass_names(
        class_to_primary_testcase_path=config.CLASS_TO_PRIMARY_TESTCASE_PATH,
        class_already_haved_testcase_path=config.CLASS_ALREADY_HAVED_TESTCASE_PATH
    )
    print("Run testcase analyzer finished.")
    return "success", None
    
def genereate_testcases(repo_path: str, target_method: str, target_class: str):
    """
    入参：
    - repo_path(str): 仓库路径
    - target_method(str): 方法名称，例如getCollection
    - target_class(str): 类名称，例如AbstractLinkedListTest
        src/test/java/org/apache/commons/collections4/AbstractLinkedListTest.java.AbstractLinkedListTest.[LinkedList<T>]getCollection()
    返回：
    - target_method_uri: 目标生成单测的方法的uri
    - generated_class_name: 生成的测试用例类名
    - results: 生成的测试用例列表, 例如：
        [
            {
                "strategy": "from_brother",
                "code": "public class TestClass { ... }"
            }
        ]
    - error: 错误信息
    """
    print('generate_testcases start.')
    repo_path = os.path.join(repo_path, ".PAGTest")
    config = RepoConfig(repo_path)
    
    status, envs = load_dotenv_file()
    if not status:
        return "", "", "failure", envs

    API_BASE, API_KEY, MODEL_NAME = envs
    
    llm = DeepSeekLLM(
        api_key=API_KEY,
        api_base=API_BASE,
        model_name=MODEL_NAME,
    )

    # 根据target_method定位method_metainfo
    data = load_json(config.METHOD_METAINFO_PATH)
    class_name = target_class.split(".")[-1]
    for method in data:
        name = '[' + method['uris'].split('[')[-1]
        if name == target_method and method['class_name'] == class_name:
            print(f"Found method {target_method} in class {class_name}")
            target_method = method
    
    if not isinstance(target_method, dict):
        print(f".Failed to find method {target_method} in class {class_name}")
        return "", "", [], f"Failed to find method {target_method} in class {class_name}"
    
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
    