import concurrent.futures
import json
from typing import List

import tiktoken

from repo_parse.utils.decorators import log_llm_interaction
from repo_parse import config
from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.llm.llm import LLM
#from repo_parse.llm.qwen_llm import QwenLLM
from repo_parse.config import CLASS_PROPERTY_DIR, FILE_PATHS_WITH_TWO_DOTS, HISTORY_TESTCASE_PATHS_PATH, PACKAGE_PREFIX, RESOLVED_METAINFO_PATH, TESTCASE_ANALYSIS_RESULT_PATH, TESTCLASS_ANALYSIS_RESULT_DIR, TESTCLASS_ANALYSIS_RESULT_PATH, TESTFILE_METAINFO_PATH
from repo_parse.context_retrieval.static_retrieval.java_static_context_retrieval import JavaStaticContextRetrieval
from repo_parse.metainfo.metainfo import MetaInfo
from repo_parse.property_graph.node_coordinator import JavaNodeCoordinator
from repo_parse.utils.data_processor import load_json, save_json
from repo_parse.prompt.testcase_analyzer import Prompt_TestSuit_Java
from repo_parse import logger


class TestCaseAnalyzer(MetaInfo):
    def __init__(
        self, 
        llm: LLM = None,
        repo_config = None,
        static_context_retrieval = None,
        testcase_analysis_result_path: str = TESTCASE_ANALYSIS_RESULT_PATH,
        testclass_analysis_result_path: str = TESTCLASS_ANALYSIS_RESULT_PATH,
    ):
        MetaInfo.__init__(self, repo_config=repo_config)
        self.tokenizer = tiktoken.get_encoding("gpt2")  
        self.token_threshold = 4096
        self.llm = llm
        self.static_context_retrieval = static_context_retrieval
        # self.testfile_metainfo = load_json(TESTFILE_METAINFO_PATH)
        if repo_config is not None:
            self.testcase_analysis_result_path = repo_config.TESTCASE_ANALYSIS_RESULT_PATH
            self.testclass_analysis_result_path = repo_config.TESTCLASS_ANALYSIS_RESULT_PATH
        else:
            self.testcase_analysis_result_path = testcase_analysis_result_path
            self.testclass_analysis_result_path = testclass_analysis_result_path
        self.all_classes = ', '.join(self.static_context_retrieval.class_map.keys())
        
    def token_count(self, input_str):
        input_tokens = self.tokenizer.encode(input_str)
        input_token_count = len(input_tokens)
        return input_token_count
        
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
    
    def extract_json(self, llm_resp: str):
        """
        Extract CMakeLists from LLM raw output.
        """
        if llm_resp.startswith("```json"):
            return llm_resp.split("```json")[1].split("```")[0]
        elif llm_resp.startswith("```"):
            return llm_resp.split("```")[1].split("```")[0]
        return llm_resp

    # @log_llm_interaction("TestCaseAnalyzer")
    def call_llm(self, system_prompt, user_input) -> str:
        full_response = self.llm.chat(system_prompt, user_input)
        return full_response
    
    def batch_high_level_analyze(self):
        raise NotImplementedError
    
    def high_level_analyze(self):
        """
        If one test function is in a test class, we analyze the test class;

        # The following cases is for Python and Go.
        else if one test function is in a file, we analyze the file;
            if file is too long,  
        """
        raise NotImplementedError

    def excute(self):
        pass

class JavaTestcaseAnalyzer(TestCaseAnalyzer):
    def __init__(
        self, 
        llm: LLM = None,
        repo_config = None
    ):
        static_context_retrieval = JavaStaticContextRetrieval(
            repo_config=repo_config
        )
        TestCaseAnalyzer.__init__(
            self, 
            llm=llm, 
            static_context_retrieval=static_context_retrieval,
            repo_config=repo_config,
        )
        self.testclass_analysis_result_dir = repo_config.TESTCLASS_ANALYSIS_RESULT_DIR

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

    def pack_static_context(self, testclass, original_string, imports, file_path):
        montage_description = ""
        resolved_ref = set()
        for _import in imports:
            if PACKAGE_PREFIX in _import:
                tokens = _import.rstrip(';').split(' ')[-1].split('.')
                class_name = tokens[-1]
                package_name = '.'.join(tokens[:-1])
                _class = self.get_class_or_none(class_name, package_name)
                # 这里暂时先只需要引入类的就行了
                if _class is not None:
                    resolved_ref.add (_class['name'])
                    class_montage = self.get_class_montage(_class)
                    montage_description += self.pack_testclass_montage_description(class_montage)
                    continue
                
                # interface = self.get_interface_or_none(class_name, package_name)
                # if interface is not None:
                #     resolved_ref.add(interface['name'])
                #     interface_montage = self.get_interface_montage(interface)
                #     montage_description += self.pack_interface_montage_description(interface_montage)
                #     continue
                
                # abstract_class = self.get_abstractclass_or_none(class_name, package_name)
                # if abstract_class is not None:
                #     resolved_ref.add(abstract_class['name'])
                #     abstract_class_montage = self.get_abstractclass_montage(abstract_class)
                #     montage_description += self.pack_abstractclass_montage_description(abstract_class_montage)

        montage_description = "\nAnd We provide you with the montage information of the imports to help you better identify." + montage_description \
            if montage_description else ""
        
        # # 1. 首先需要引入被测类的montage啊，让他直到有哪些方法。
        # class_montage = self.get_class_montage(testclass)
        # testclass_montage_description = self.pack_testclass_montage_description(class_montage)
        
        # 同一个package中的引用信息提供一下
        # TODO: 这里也需要进行判断的，如果是Class.XXXX，那就只需要引入XXXX就行了。
        unresolved_refs = self.static_context_retrieval.find_unresolved_refs(original_string)
        
        unresolved_refs = set(unresolved_refs) - resolved_ref - set(self.static_context_retrieval.keywords_and_builtin)
        
        package_class_montages = self.static_context_retrieval.pack_package_info(list(unresolved_refs), file_path, original_string)
        package_class_montages_description = self.pack_package_class_montages_description(package_class_montages)
        
        # import过来的类，montage信息要不要全部提供？太多了。暂时先不管了。
        
        imports_str = '\n'.join(imports)
        input_str = imports_str + original_string + montage_description
            
        # 这里可以加一个计算token的措施，如果token 超过阈值，就不加package的了
        input_token_count = self.token_count(input_str + package_class_montages_description)
        if input_token_count < 8182:
            pass
            # 先暂时跳过这个吧
            # input_str += package_class_montages_description
        else:
            logger.warning(f"Token count of input string for testcase analysis is too large: {input_token_count}")
        
        return input_str

    def high_level_analyze(self, filter_list: List[str] = []):
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
            if filter_list and testclass['file_path'] not in filter_list:
                continue

            if testclass['uris'] != "src/test/java/unit/websocketapi/TestSignedRequests.java.TestSignedRequests":
                continue
            try:
                file_path = testclass['uris'].split('.java')[0] + '.java'
                imports = self.get_imports(file_path=file_path)
                imports_str = '\n'.join(imports)
                original_string = testclass['original_string']
                                
                user_input = self.pack_static_context(testclass=testclass, original_string=original_string, 
                                                      imports=imports, file_path=file_path)
                
                full_response = self.call_llm(system_prompt=Prompt_TestSuit_Java, user_input=user_input)
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

    def merge_testclass_analysis_result(self, original_path, incremental_path, save_path):
        original_data = load_json(original_path)
        incremental_data = load_json(incremental_path)
        original_data.extend(incremental_data)
        data = original_data
        save_json(save_path, data)
        logger.info(f"Merged testclass analysis result saved to {save_path}")

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
        save_json(file_path=TESTCLASS_ANALYSIS_RESULT_DIR + str(round_number) + 'failures.json', data=fails)
        
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
            # if file_path not in success_testcase_paths:
            #     continue
            
            if file_path in testclass_analysis_result_paths:
                continue

            try:
                file_path = testclass['uris'].split('.java')[0] + '.java'
                imports = self.get_imports(file_path=file_path)
                imports_str = '\n'.join(imports)
                original_string = testclass['original_string']

                user_input = self.pack_static_context(testclass=testclass, original_string=original_string, 
                                                      imports=imports, file_path=file_path)

                full_response = self.call_llm(system_prompt=Prompt_TestSuit_Java, user_input=user_input)
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
        save_json(file_path=TESTCLASS_ANALYSIS_RESULT_DIR + str(round_number) + 'failures.json', data=fails)

def run_testcase_analyzer(analyzer: TestCaseAnalyzer, is_batch: bool = False, use_file_paths_with_two_dots: bool = False):
    logger.info("Starting testcase analyzer...")
    # analyzer.excute()
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


if __name__ == "__main__":
    llm = DeepSeekLLM()
    # llm = QwenLLM()
    # analyzer = PythonTestcaseAnalyzer(
    #     llm=llm,
    # )
    analyzer = JavaTestcaseAnalyzer(
        llm=llm,
    )
    
    # analyzer.excute()
    analyzer.high_level_analyze()
    # analyzer.reslove_history_testcase_paths(analyzer.testclass_metainfo, update=False)
    # analyzer.merge_testclass_analysis_result(
    #     original_path=r"/home/zhangzhe/APT/repo_parse/outputs/hospital-management-api/testclass_analysis_result.json",
    #     incremental_path=r"/home/zhangzhe/APT/repo_parse/outputs/hospital-management-api/round_1/testclass_analysis_result.json",
    #     save_path=r"/home/zhangzhe/APT/repo_parse/outputs/hospital-management-api/testclass_analysis_result.json"
    # )
    # analyzer.get_unresolved_refs()
    
    # testclass_analysis_result_paths = [res['file_path'] for res in load_json(TESTCLASS_ANALYSIS_RESULT_PATH)]
    # analyzer.batch_incremental_high_level_analyze(testclass_analysis_result_paths=testclass_analysis_result_paths, 
    #                                                 save_path="/home/zhangzhe/APT/repo_parse/outputs/commons-cli/round_1/testclass_analysis_result.json",
    #                                                 round_number=1)
    
    # coordinator = JavaNodeCoordinator()
    # coordinator.map_method_to_testcase(coordinator.testclass_analysis_result)
    # coordinator.map_class_to_testcase()
    
    # analyzer.merge_testclass_analysis_result(original_path=r"/home/zhangzhe/APT/repo_parse/outputs/binance-connector-java-3/testclass_analysis_result.json",
    #                                          incremental_path=r"/home/zhangzhe/APT/repo_parse/outputs/binance-connector-java-3/round_1/testclass_analysis_result.json",
    #                                          save_path=r"/home/zhangzhe/APT/repo_parse/outputs/binance-connector-java-3/testclass_analysis_result.json")
        
    print("Finished")
    