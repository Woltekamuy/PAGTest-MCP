
from collections import defaultdict
from typing import Dict, List

from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.llm.llm import LLM
#from repo_parse.llm.qwen_llm import QwenLLM
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
    def __init__(
        self, 
        llm: LLM = None,
        repo_config = None,
        testcase_analysis_result_path=TESTCASE_ANALYSIS_RESULT_PATH,
        testclass_analysis_result_path=TESTCLASS_ANALYSIS_RESULT_PATH,
        class_property_path=CLASS_PROPERTY_PATH,
        node_coordinator_result_path=NODE_COORDINATOR_RESULT_PATH,
        part_unmapped_nodes_path=PART_UNMAPPED_NODES_PATH,
        full_unmapped_nodes_path=FULL_UNMAPPED_NODES_PATH,
        node_to_testcase_path=NODE_TO_TESTCASE_PATH,
        static_context_retrieval = None,
        method_to_primary_testcase_path=METHOD_TO_PRIMARY_TESTCASE_PATH,
        method_to_relevant_testcase_path=METHOD_TO_RELEVANT_TESTCASE_PATH,
    ):
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
        if repo_config is not None:
            self.class_to_primary_testcase_path = repo_config.CLASS_TO_PRIMARY_TESTCASE_PATH
            self.class_to_relevant_testcase_path = repo_config.CLASS_TO_RELEVANT_TESTCASE_PATH
        else:
            self.class_to_primary_testcase_path = CLASS_TO_PRIMARY_TESTCASE_PATH
            self.class_to_relevant_testcase_path = CLASS_TO_RELEVANT_TESTCASE_PATH

    def excute(self):
        pass

    def get_exsiting_brother_having_testcase(
        self,
        inherit_tree_path: str = INHERIT_TREE_PATH,
        brother_enhancements_path: str = BROTHER_ENHANCEMENTS_PATH
    ):
        data = load_json(self.class_to_primary_testcase_path)
        classes = data.keys()
        inherit_tree = load_json(inherit_tree_path)
        brother_relations = inherit_tree['brother_relations']
        res = defaultdict(list)
        for k, v in brother_relations.items():
            if k in classes:
                for brother in v:                   
                    methods = self.get_common_methods(child=brother)
                    if methods is None:
                        continue
                    
                    temp_dict = {
                        "methods": [],
                        "class": "",
                    }
                    testcases = data[k]
                    method_names = set()
                    pruned_methods = [method.split(']')[-1] for method in methods]
                    for testcase in testcases:
                        if testcase['method_name'] in pruned_methods:
                            if testcase['method_name'] not in method_names:
                                method_names.add(testcase['method_name'])
                                temp_dict['methods'].append(testcase)

                    temp_dict['class'] = k
                    res[brother].append(temp_dict)

        save_json(file_path=brother_enhancements_path, data=res)
        logger.info(f'Brother enhancements saved to {brother_enhancements_path}')

    def get_exsiting_parent_child_having_testcase(
        self,
        inherit_tree_path: str = INHERIT_TREE_PATH,
        parent_enhancements_path: str = PARENT_ENHANCEMENTS_PATH,
        child_enhancements_path: str = CHILD_ENHANCEMENTS_PATH
    ):
        data = load_json(self.class_to_primary_testcase_path)
        classes = data.keys()
        inherit_tree = load_json(inherit_tree_path)
        child_to_parent = inherit_tree.get('parents', {})
        parent_enhancements = defaultdict(list)  
        child_enhancements = defaultdict(list)  

        for child, parent in child_to_parent.items():
            if parent in classes:
                methods = self.get_common_methods(child=child)
                if methods is None:
                    continue
                temp_dict = {
                    "methods": [],
                    "class": parent,
                }
                testcases = data[parent]
                method_names = set()
                pruned_methods = [method.split(']')[-1] for method in methods]
                for testcase in testcases:
                    if testcase['method_name'] in pruned_methods:
                        if testcase['method_name'] not in method_names:
                            method_names.add(testcase['method_name'])
                            temp_dict['methods'].append(testcase)

                parent_enhancements[child].append(temp_dict)

            if child in classes:
                methods = self.get_common_methods(child=child)
                if methods is None:
                    continue

                temp_dict = {
                    "methods": [],
                    "class": child,
                }
                testcases = data[child]
                method_names = set()
                pruned_methods = [method.split(']')[-1] for method in methods]
                for testcase in testcases:
                    if testcase['method_name'] in pruned_methods:
                        if testcase['method_name'] not in method_names:
                            method_names.add(testcase['method_name'])
                            temp_dict['methods'].append(testcase)

                child_enhancements[parent].append(temp_dict)

        save_json(file_path=parent_enhancements_path, data=parent_enhancements)
        save_json(file_path=child_enhancements_path, data=child_enhancements)
        logger.info(f'Parent enhancements saved to {parent_enhancements_path}')
        logger.info(f'Child enhancements saved to {child_enhancements_path}')
        
    def get_exsiting_interface_brother_having_testcase(
        self,
        interface_brother_relations_path: str = INTERFACE_BROTHER_RELATIONS_PATH,
        interface_brother_enhancements_path: str = INTERFACE_BROTHER_ENHANCEMENTS_PATH
    ):
        data = load_json(self.class_to_primary_testcase_path)
        classes = data.keys()
        interface_brother_relations = load_json(interface_brother_relations_path)
        res = defaultdict(list) 
        for item in interface_brother_relations:
            implementations = item['implementations']
            for implementation in implementations:
                if implementation.split('.')[-1] in classes:
                    for brother in implementations:
                        if brother == implementation:
                            continue
                        methods = item['methods']
                        temp_dict = {
                            "methods": [],
                            "interface_brother": implementation,
                        }
                        testcases = data[implementation.split('.')[-1]]
                        method_names = set()
                        pruned_methods = [method.split(']')[-1] for method in methods]
                        for testcase in testcases:
                            if testcase['method_name'] in pruned_methods:
                                if testcase['method_name'] not in method_names:
                                    method_names.add(testcase['method_name'])
                                    temp_dict['methods'].append(testcase)
                        res[brother.split('.')[-1]].append(temp_dict)

        save_json(file_path=interface_brother_enhancements_path, data=res)
        logger.info(f'Interface brother enhancements saved to {interface_brother_enhancements_path}')

    def get_testcase_analysis_result(self, file_path: str, testcase_name: str) -> Dict:
        for testcase in self.testcase_analysis_result:
            if testcase['test_case_name'] == testcase_name and testcase['file'] == file_path:
                return testcase
        logger.exception(f"testcase analysis result of {testcase_name} in file {file_path} can not be found!")
        raise Exception(f"testcase analysis result of {testcase_name} in file {file_path} can not be found!")
            
    def get_class_property(self, class_name: str) -> Dict:
        for _class in self.class_property:
            if _class['class_name'] == class_name:
                return _class

    def get_tested_class(self, file_path):
        for testclass in self.testclass_analysis_result:
            if testclass['file_path'] != file_path or testclass['testclass_name'] != testclass['name']:
                continue
            
            testclass_set = set()
            test_cases = testclass['test_cases']
            for testcase in test_cases:
                tested = testcase['tested']
                for item in tested:
                    tested_class_name = item.split('.')[0] if '.' in item else item
                    testclass_set.add(tested_class_name)
                
            return list(testclass_set)
    
    def map_method_to_testcase(self, testclass_analysis_result, save: bool = True):
        method_to_primary_testcase = {}
        method_to_relevant_testcases = {}
        
        for testclass_info in testclass_analysis_result:
            if 'test_cases' not in testclass_info:
                logger.error(f"test_cases not found in testclass_info: {testclass_info}")
                continue

            testclass_name = testclass_info['testclass_name']
            for testcase in testclass_info['test_cases']:
                primary_tested = testcase.get('primary_tested', [])
                testcase_name = testcase['name']
                for tested in primary_tested:
                    method_signature = tested.split('.')[-1] if '.' in tested else tested
                    method_signature = method_signature.replace(' ', '')
                    if method_signature not in method_to_primary_testcase:
                        method_to_primary_testcase[method_signature] = []
                    method_to_primary_testcase[method_signature].append({
                        'class_name': tested.split('.')[0] if '.' in tested else tested,
                        'file_path': testclass_info['file_path'],
                        'testclass_name': testclass_name,
                        'testcase_name': testcase_name
                    })
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
        logger.info("Mapping class to testcase")
        method_to_primary_testcase = load_json(self.method_to_primary_testcase_path)
        method_to_relevant_testcase = load_json(self.method_to_relevant_testcase_path)
        
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
                
        save_json(file_path=self.class_to_primary_testcase_path, data=class_to_primary_testcase)
        save_json(file_path=self.class_to_relevant_testcase_path, data=class_to_relevant_testcase)
        logger.info("Mapping class to testcase finished")

    def solove_exsisting_enhencement(self, full_unmapped_nodes, save: bool = True):
        raise NotImplementedError


class JavaNodeCoordinator(NodeCoordinator):
    def __init__(
        self, 
        llm: LLM = None,
        repo_config = None,
        record_metainfo_path: str = RECORD_METAINFO_PATH,
        interface_metainfo_path: str = INTERFACE_METAINFO_PATH, 
        packages_metainfo_path: str = PACKAGES_METAINFO_PATH,
        testcase_analysis_result_path=TESTCASE_ANALYSIS_RESULT_PATH,
        testclass_analysis_result_path=TESTCLASS_ANALYSIS_RESULT_PATH,
        class_property_path=CLASS_PROPERTY_PATH,
        node_coordinator_result_path=NODE_COORDINATOR_RESULT_PATH,
        part_unmapped_nodes_path=PART_UNMAPPED_NODES_PATH,
        full_unmapped_nodes_path=FULL_UNMAPPED_NODES_PATH,
        node_to_testcase_path=NODE_TO_TESTCASE_PATH,
        method_to_primary_testcase_path=METHOD_TO_PRIMARY_TESTCASE_PATH,
        method_to_relevant_testcase_path=METHOD_TO_RELEVANT_TESTCASE_PATH,
    ):
        static_context_retrieval = JavaStaticContextRetrieval(
            repo_config=repo_config,
            record_metainfo_path=record_metainfo_path,
            interface_metainfo_path=interface_metainfo_path,
            packages_metainfo_path=packages_metainfo_path
        )
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
    logger.info("Node Coordinator Start!")
    
    coordinator = coordinator()
    
    testclass_analysis_result = load_json(TESTCLASS_ANALYSIS_RESULT_PATH)
    results = coordinator.map_method_to_testcase(testclass_analysis_result)
    coordinator.map_class_to_testcase()
    coordinator.get_exsiting_brother_having_testcase()
    coordinator.get_exsiting_parent_child_having_testcase()
    coordinator.get_exsiting_interface_brother_having_testcase()

    logger.info("Node Coordinator Done!")
