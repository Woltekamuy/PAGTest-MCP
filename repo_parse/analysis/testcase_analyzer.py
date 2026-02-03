# ============================================
# 模块说明：
# 本模块用于对代码仓库中的测试用例（主要是 Java TestClass）进行
# 静态上下文增强 + LLM 语义分析，并将分析结果结构化存储。
#
# 核心能力包括：
# 1. 基于静态分析的上下文拼装（imports / unresolved refs / montage）
# 2. 基于 LLM 的测试类语义分析
# 3. 支持批量分析 / 增量分析 / 并发执行
# 4. 分析结果的持久化与合并
#
# 该模块是 repo_parse 中 TestCase / TestClass 分析流水线的核心组件之一
# ============================================

import concurrent.futures
import json
from typing import List

import tiktoken

# LLM 交互日志装饰器（当前未启用）
from repo_parse.utils.decorators import log_llm_interaction

# 全局配置
from repo_parse import config
from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.llm.llm import LLM
#from repo_parse.llm.qwen_llm import QwenLLM

# 各类路径与配置常量
from repo_parse.config import (
    CLASS_PROPERTY_DIR,
    FILE_PATHS_WITH_TWO_DOTS,
    HISTORY_TESTCASE_PATHS_PATH,
    PACKAGE_PREFIX,
    RESOLVED_METAINFO_PATH,
    TESTCASE_ANALYSIS_RESULT_PATH,
    TESTCLASS_ANALYSIS_RESULT_DIR,
    TESTCLASS_ANALYSIS_RESULT_PATH,
    TESTFILE_METAINFO_PATH
)

# Java 静态上下文检索器
from repo_parse.context_retrieval.static_retrieval.java_static_context_retrieval import JavaStaticContextRetrieval

# 元信息基类（提供 class / interface / import 等能力）
from repo_parse.metainfo.metainfo import MetaInfo

# 属性图节点协调器（用于后续 testcase ↔ 方法 / 类映射）
from repo_parse.property_graph.node_coordinator import JavaNodeCoordinator

# JSON 工具函数
from repo_parse.utils.data_processor import load_json, save_json

# Java TestSuite 分析 Prompt
from repo_parse.prompt.testcase_analyzer import Prompt_TestSuit_Java

# 日志模块
from repo_parse import logger


# ============================================================
# TestCaseAnalyzer
# ============================================================
# 抽象的测试用例分析器基类
# - 提供 LLM 调用、token 计数、结果抽取等通用能力
# - 针对不同语言（Java / Python / Go）由子类实现具体逻辑
# ============================================================
class TestCaseAnalyzer(MetaInfo):
    def __init__(
        self,
        llm: LLM = None,
        repo_config = None,
        static_context_retrieval = None,
        testcase_analysis_result_path: str = TESTCASE_ANALYSIS_RESULT_PATH,
        testclass_analysis_result_path: str = TESTCLASS_ANALYSIS_RESULT_PATH,
    ):
        # 初始化仓库元信息
        MetaInfo.__init__(self, repo_config=repo_config)

        # 使用 GPT-2 tokenizer 进行 token 估算
        self.tokenizer = tiktoken.get_encoding("gpt2")
        self.token_threshold = 4096

        # LLM 实例
        self.llm = llm

        # 静态上下文检索器（语言相关）
        self.static_context_retrieval = static_context_retrieval

        # 根据 repo_config 动态覆盖结果路径
        if repo_config is not None:
            self.testcase_analysis_result_path = repo_config.TESTCASE_ANALYSIS_RESULT_PATH
            self.testclass_analysis_result_path = repo_config.TESTCLASS_ANALYSIS_RESULT_PATH
        else:
            self.testcase_analysis_result_path = testcase_analysis_result_path
            self.testclass_analysis_result_path = testclass_analysis_result_path

        # 所有类名集合（用于 Prompt 辅助）
        self.all_classes = ', '.join(self.static_context_retrieval.class_map.keys())

    # ------------------------------------------------------------
    # token 计数工具函数
    # ------------------------------------------------------------
    def token_count(self, input_str):
        input_tokens = self.tokenizer.encode(input_str)
        input_token_count = len(input_tokens)
        return input_token_count

    # ------------------------------------------------------------
    # 从 LLM 原始输出中解析 JSON 结果
    # ------------------------------------------------------------
    def extract(self, full_response):
        """
        Extract fuzztest driver from LLM raw output.
        """
        resp_json: str = self.extract_json(full_response)
        try:
            resp: dict = json.loads(resp_json)
            return resp
        except Exception as e:
            logger.exception(f'Error while extract json from LLM raw output: {e}')
            return {}

    # ------------------------------------------------------------
    # 处理 ```json / ``` 包裹的 LLM 输出
    # ------------------------------------------------------------
    def extract_json(self, llm_resp: str):
        """
        Extract CMakeLists from LLM raw output.
        """
        if llm_resp.startswith("```json"):
            return llm_resp.split("```json")[1].split("```")[0]
        elif llm_resp.startswith("```"):
            return llm_resp.split("```")[1].split("```")[0]
        return llm_resp

    # ------------------------------------------------------------
    # LLM 调用封装
    # ------------------------------------------------------------
    # @log_llm_interaction("TestCaseAnalyzer")
    def call_llm(self, system_prompt, user_input) -> str:
        full_response = self.llm.chat(system_prompt, user_input)
        return full_response

    # 批量分析（由子类实现）
    def batch_high_level_analyze(self):
        raise NotImplementedError

    # 单次分析（由子类实现）
    def high_level_analyze(self):
        """
        If one test function is in a test class, we analyze the test class;

        # The following cases is for Python and Go.
        else if one test function is in a file, we analyze the file;
            if file is too long,
        """
        raise NotImplementedError

    # 预留执行入口
    def excute(self):
        pass


# ============================================================
# JavaTestcaseAnalyzer
# ============================================================
# Java 语言专用的 TestCaseAnalyzer 实现
# - 负责 Java TestClass 的静态上下文拼装
# - 调用 LLM 进行测试语义分析
# ============================================================
class JavaTestcaseAnalyzer(TestCaseAnalyzer):
    def __init__(
        self,
        llm: LLM = None,
        repo_config = None
    ):
        # 初始化 Java 静态上下文检索器
        static_context_retrieval = JavaStaticContextRetrieval(
            repo_config=repo_config
        )

        # 调用父类初始化
        TestCaseAnalyzer.__init__(
            self,
            llm=llm,
            static_context_retrieval=static_context_retrieval,
            repo_config=repo_config,
        )

        # TestClass 分析结果输出目录
        self.testclass_analysis_result_dir = repo_config.TESTCLASS_ANALYSIS_RESULT_DIR

    # ------------------------------------------------------------
    # 记录历史已分析的 testcase 路径
    # ------------------------------------------------------------
    def reslove_history_testcase_paths(
        self,
        testclass,
        history_testcase_paths_path: str = config.HISTORY_TESTCASE_PATHS_PATH,
        update=False
    ):
        file_paths = [_class['file_path'] for _class in testclass]
        res = {'history_testcase_paths': file_paths}
        if update:
            history_testcase_paths = load_json(history_testcase_paths_path)
            res['history_testcase_paths'].extend(history_testcase_paths['history_testcase_paths'])
        save_json(history_testcase_paths_path, res)
        logger.info(f"History testcase paths saved")

    # ------------------------------------------------------------
    # 打包 TestClass montage 描述（供 LLM 使用）
    # ------------------------------------------------------------
    def pack_testclass_montage_description(self, class_montage):
        """
        {
            "class_name": _class['name'],
            "methods_signature": _class['methods'],
            "fields": [field['attribute_expression'] for field in _class['fields']]
        }
        """
        return (
            "" +
            self.pack_class_montage_description(class_montage)
        )

    # ------------------------------------------------------------
    # 单个 TestClass 分析主逻辑
    # ------------------------------------------------------------
    def analyze_testclass(self, testclass):
        """
        这个是单个的分析，接受一个testclass的metainfo
        """
        name = testclass['name']
        try:
            file_path = testclass['uris'].split('.java')[0] + '.java'
            imports = self.get_imports(file_path=file_path)
            imports_str = '\n'.join(imports)
            original_string = testclass['original_string']

            # 这里给错了啊！！。。。

            user_input = self.pack_static_context(testclass=testclass, original_string=original_string,
                                                  imports=imports, file_path=file_path)

            full_response = self.call_llm(system_prompt=Prompt_TestSuit_Java, user_input=user_input)

            resp_dict = self.extract(full_response)

            testclass_info = {
                'file_path': file_path,
                'testclass_name': name,
                'dependencies': imports
            }
            return {**testclass_info, **resp_dict}
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            logger.exception(f'Analyze testclass {name} failed: {e}')
            return {'testclass_uris': testclass["uris"], 'error': str(e)}

    # ------------------------------------------------------------
    # 并发批量 TestClass 分析
    # ------------------------------------------------------------
    def batch_high_level_analyze(
        self,
        filter_list=[],
        testclass_analysis_result_dir: str = TESTCLASS_ANALYSIS_RESULT_DIR,
    ):
        results = []
        fails = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            future_to_testclass = {}
            for testclass in self.testclass_metainfo:
                if filter_list and testclass['file_path'] not in filter_list:
                    continue
                future = executor.submit(self.analyze_testclass, testclass)
                future_to_testclass[future] = testclass

            for future in concurrent.futures.as_completed(future_to_testclass):
                testclass = future_to_testclass[future]
                try:
                    res = future.result()
                    if 'error' not in res:
                        results.append(res)
                        file_name = testclass['uris'].replace('/', '_') + '.json'
                        save_json(file_path=testclass_analysis_result_dir + file_name, data=res)
                        logger.info(f"Analyze testclass {testclass['name']} finished")
                    else:
                        fails.append(res)
                except Exception as e:
                    fails.append({'testclass_uris': testclass["uris"], 'error': str(e.stdout)})
                    logger.exception(f'Analyze testclass {testclass["name"]} failed: {e.stdout}')

        save_json(file_path=self.testclass_analysis_result_path, data=results)
        save_json(file_path=testclass_analysis_result_dir + 'failures.json', data=fails)

    # ------------------------------------------------------------
    # 构造 LLM 所需的静态上下文输入
    # ------------------------------------------------------------
    def pack_static_context(self, testclass, original_string, imports, file_path):
        montage_description = ""
        resolved_ref = set()

        # 处理 import 中可解析的类
        for _import in imports:
            if PACKAGE_PREFIX in _import:
                tokens = _import.rstrip(';').split(' ')[-1].split('.')
                class_name = tokens[-1]
                package_name = '.'.join(tokens[:-1])
                _class = self.get_class_or_none(class_name, package_name)
                if _class is not None:
                    resolved_ref.add (_class['name'])
                    class_montage = self.get_class_montage(_class)
                    montage_description += self.pack_testclass_montage_description(class_montage)
                    continue

        # montage 描述仅在存在时拼接
        montage_description = (
            "\nAnd We provide you with the montage information of the imports to help you better identify."
            + montage_description
            if montage_description else ""
        )

        # # 1. 首先需要引入被测类的montage啊，让他直到有哪些方法。
        # class_montage = self.get_class_montage(testclass)
        # testclass_montage_description = self.pack_testclass_montage_description(class_montage)

        # 同一个package中的引用信息提供一下
        # TODO: 这里也需要进行判断的，如果是Class.XXXX，那就只需要引入XXXX就行了。
        # 查找 unresolved reference（同包引用）
        unresolved_refs = self.static_context_retrieval.find_unresolved_refs(original_string)
        unresolved_refs = (
            set(unresolved_refs)
            - resolved_ref
            - set(self.static_context_retrieval.keywords_and_builtin)
        )

        package_class_montages = self.static_context_retrieval.pack_package_info(
            list(unresolved_refs),
            file_path,
            original_string
        )
        package_class_montages_description = self.pack_package_class_montages_description(package_class_montages)

        # import过来的类，montage信息要不要全部提供？太多了。暂时先不管了。

        imports_str = '\n'.join(imports)
        input_str = imports_str + original_string + montage_description

        # Token 数量控制（避免 Prompt 过长）
        input_token_count = self.token_count(input_str + package_class_montages_description)
        if input_token_count < 8182:
            pass
        else:
            logger.warning(
                f"Token count of input string for testcase analysis is too large: {input_token_count}"
            )

        return input_str

    # ------------------------------------------------------------
    # 非并发版本的高层分析（调试 / 定向使用）
    # ------------------------------------------------------------
    def high_level_analyze(self, filter_list: List[str] = []):
        results = []
        fails = []
        for testclass in self.testclass_metainfo:
            name = testclass['name']
            if filter_list and testclass['file_path'] not in filter_list:
                continue

            if testclass['uris'] != "src/test/java/unit/websocketapi/TestSignedRequests.java.TestSignedRequests":
                continue
            try:
                file_path = testclass['uris'].split('.java')[0] + '.java'
                imports = self.get_imports(file_path=file_path)
                imports_str = '\n'.join(imports)
                original_string = testclass['original_string']

                user_input = self.pack_static_context(
                    testclass=testclass,
                    original_string=original_string,
                    imports=imports,
                    file_path=file_path
                )

                full_response = self.call_llm(
                    system_prompt=Prompt_TestSuit_Java,
                    user_input=user_input
                )
                resp_dict = self.extract(full_response)

                testclass_info = {
                    'file_path': file_path,
                    'testclass_name': name,
                    'dependencies': imports
                }
                res = {**testclass_info, **resp_dict}
                results.append(res)

                file_name = testclass['uris'].replace('/', '_') + '.json'
                save_json(file_path=self.testclass_analysis_result_dir + file_name, data=res)
                logger.info(f"Analyze testclass {name} finished")
            except Exception as e:
                fails.append({'testclass_uris': testclass["uris"], 'error': str(e.stdout)})
                logger.exception(f'Analyze testclass {name} failed: {e.stdout}')

        save_json(file_path=self.testclass_analysis_result_path, data=results)
        save_json(file_path=self.testclass_analysis_result_dir + 'failures.json', data=fails)

    # ------------------------------------------------------------
    # 合并多轮 TestClass 分析结果
    # ------------------------------------------------------------
    def merge_testclass_analysis_result(self, original_path, incremental_path, save_path):
        original_data = load_json(original_path)
        incremental_data = load_json(incremental_path)
        original_data.extend(incremental_data)
        data = original_data
        save_json(save_path, data)
        logger.info(f"Merged testclass analysis result saved to {save_path}")

    # ------------------------------------------------------------
    # 并发增量分析
    # ------------------------------------------------------------
    def batch_incremental_high_level_analyze(self, testclass_analysis_result_paths, save_path, round_number):
        results = []
        fails = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            testclass_metainfo = []
            for testclass in self.testclass_metainfo:
                file_path = testclass['file_path']
                if file_path not in testclass_analysis_result_paths:
                    testclass_metainfo.append(testclass)

            future_to_testclass = {executor.submit(self.analyze_testclass, testclass): testclass for testclass in testclass_metainfo}
            for future in concurrent.futures.as_completed(future_to_testclass):
                testclass = future_to_testclass[future]
                try:
                    res = future.result()
                    if 'error' not in res:
                        results.append(res)
                        file_name = testclass['uris'].replace('/', '_') + '.json'
                        save_json(file_path=TESTCLASS_ANALYSIS_RESULT_DIR + file_name, data=res)
                        logger.info(f"Analyze testclass {testclass['name']} finished")
                    else:
                        fails.append(res)
                except Exception as e:
                    fails.append({'testclass_uris': testclass["uris"], 'error': str(e)})
                    logger.exception(f'Analyze testclass {testclass["name"]} failed: {e}')

        save_json(file_path=save_path, data=results)
        logger.info("Incremental high level analyze finished")
        save_json(
            file_path=TESTCLASS_ANALYSIS_RESULT_DIR + str(round_number) + 'failures.json',
            data=fails
        )


    # ------------------------------------------------------------
    # 串行增量分析
    # ------------------------------------------------------------

    def incremental_high_level_analyze(self, testclass_analysis_result_paths, save_path, round_number):
        """
        If one test function is in a test class, we analyze the test class;

        # The following cases is for Python and Go.
        else if one test function is in a file, we analyze the file;
            if file is too long,
        """
        results = []
        fails = []

        for testclass in self.testclass_metainfo:
            name = testclass['name']
            file_path = testclass['file_path']

            if file_path in testclass_analysis_result_paths:
                continue

            try:
                file_path = testclass['uris'].split('.java')[0] + '.java'
                imports = self.get_imports(file_path=file_path)
                imports_str = '\n'.join(imports)
                original_string = testclass['original_string']

                user_input = self.pack_static_context(
                    testclass=testclass,
                    original_string=original_string,
                    imports=imports,
                    file_path=file_path
                )

                full_response = self.call_llm(
                    system_prompt=Prompt_TestSuit_Java,
                    user_input=user_input
                )
                resp_dict = self.extract(full_response)
                testclass_info = {
                    'file_path': file_path,
                    'testclass_name': name,
                    'dependencies': imports
                }
                res = {**testclass_info, **resp_dict}
                results.append(res)

                file_name = testclass['uris'].replace('/', '_') + '.json'
                save_json(file_path=TESTCLASS_ANALYSIS_RESULT_DIR + file_name, data=res)
                logger.info(f"Analyze testclass {name} finished")
            except Exception as e:
                fails.append({'testclass_uris': testclass["uris"], 'error': str(e)})
                logger.exception(f'Analyze testclass {name} failed: {e}')

        save_json(file_path=save_path, data=results)
        logger.info("Incremental high level analyze finished")
        save_json(
            file_path=TESTCLASS_ANALYSIS_RESULT_DIR + str(round_number) + 'failures.json',
            data=fails
        )


# ============================================================
# 统一运行入口
# ============================================================
def run_testcase_analyzer(
    analyzer: TestCaseAnalyzer,
    is_batch: bool = False,
    use_file_paths_with_two_dots: bool = False
):
    logger.info("Starting testcase analyzer...")
    analyzer = analyzer()
    analyzer.reslove_history_testcase_paths(analyzer.testclass_metainfo, update=False)

    if not is_batch:
        analyzer.high_level_analyze()
    else:
        if use_file_paths_with_two_dots:
            with open (FILE_PATHS_WITH_TWO_DOTS, 'r') as f:
                filter_list = f.read().splitlines()
        else:
            filter_list = []
        analyzer.batch_high_level_analyze(filter_list=filter_list)

    logger.info("Testcase analyzer finished!")


# ============================================================
# CLI 入口
# ============================================================
if __name__ == "__main__":
    llm = DeepSeekLLM()
    analyzer = JavaTestcaseAnalyzer(
        llm=llm,
    )
    analyzer.high_level_analyze()
    print("Finished")
