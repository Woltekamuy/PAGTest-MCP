"""
Property Graph Retrieval Module

该模块定义了一套用于从“属性图（Property Graph）”中检索上下文信息的抽象与实现，
主要面向**函数级 / 类级 / 仓库级**三种粒度的上下文构建，服务于自动化测试生成、
上下文感知代码理解以及 Prompt 组装等场景。

核心设计目标：
- 将函数、类、仓库之间的结构化关系（依赖、增强、兄弟类等）统一抽象为 Context
- 将已有 TestCase 作为一等公民纳入上下文
- 为不同语言（Python / Java）提供可扩展的 Retrieval 实现
"""

from typing import Dict, List, Optional, Tuple

from repo_parse.config import BROTHER_RELATIONS_PATH, FUNC_RELATION_PATH, NODE_TO_TESTCASE_PATH, PROPERTY_GRAPH_PATH
from repo_parse.metainfo.metainfo import MetaInfo
from repo_parse.metainfo.model import MethodSignature, TestCase
from repo_parse.utils.data_processor import get_single_value_in_dict, load_json
from repo_parse import logger


class ContextType:
    """
    Context 的来源层级枚举。

    - function: 函数级上下文
    - class:    类级上下文
    - repo:     仓库级上下文
    """
    function = "function"
    _class = "class"
    repo = "repo"


class ContextInfo:
    def __init__(self, relation = None, testcases: List[TestCase] = None):
        """
        Context 的最小信息单元。

        用于承载：
        - 函数/方法之间的关系描述（relation）
        - 与该上下文关联的测试用例（testcases）
        relation:
            {
                "class_name": "Deduper",
                "relationship_type": "Dependency",
                "description": "The query method records keys of duplicates when the record_duplicates flag is set, which are then accessible through the keys_of_duplicates method.",
                "enhancers": [
                    "query"
                ],
                "enhanced_methods": [
                    "keys_of_duplicates"
                ]
            }
        """
        self.relation = relation
        self.testcases = testcases

class Context:
    """
    表示某一层级（函数 / 类 / 仓库）的完整上下文。

    属性说明：
    - _from:   上下文来源层级（ContextType）
    - to:      目标函数 / 方法名
    - what:    可选的语义描述字段
    - content: 实际上下文内容（ContextInfo 或其映射）
    """

    def __init__(self, _from: str, to: str, what: str = '',
                 content: Dict[str, ContextInfo] | ContextInfo = None) -> None:
        self._from = _from
        self.to = to
        self.what = what
        self.content = content


class PropertyContext:
    """
    用于聚合三种层级上下文的容器对象。

    - func_level_context:  函数级上下文
    - class_level_context: 类级上下文
    - repo_level_context:  仓库级上下文
    """

    def __init__(self,
                 func_level_context = None,
                 class_level_context = None,
                 repo_level_context = None):
        self.func_level_context = func_level_context
        self.class_level_context = class_level_context
        self.repo_level_context = repo_level_context


class PropertyGraphRetrieval(MetaInfo):
    """
    属性图检索的抽象基类。

    提供：
    - 函数 / 类 / 仓库层级的检索接口
    - 通用的数据加载与结构定义

    不同语言的实现应在此基础上进行扩展。
    """

    def __init__(self,
                 node_to_testcase_path: str = NODE_TO_TESTCASE_PATH,
                 func_relation_path: str = FUNC_RELATION_PATH,
                 brother_relation_path: str = BROTHER_RELATIONS_PATH) -> None:
        MetaInfo.__init__(self)

        # 节点（类 / 方法）到测试用例的映射
        # self.node_to_testcase = load_json(node_to_testcase_path)
        self.node_to_testcase = []

        # 函数级关系图（如依赖 / 增强）
        # self.func_relation = load_json(func_relation_path)
        self.func_relation = []

        # 类级兄弟关系图
        self.brother_relation = load_json(brother_relation_path)

    def pack_func_property_context(self, method_signature: MethodSignature):
        """
        根据方法签名组装完整的 Property Context。

        该方法通常负责：
        - 调用不同层级的 retrieval
        - 对结果进行聚合与封装
        """
        pass

    def func_level_retrieval(self, func_uri: str):
        """
        函数级上下文检索接口。

        func_uri 示例：
            "ClassName.method_name"
        """
        pass

    def repo_level_retrieval(self, func_uri: str):
        """
        仓库级上下文检索。

        当前实现：
        - 返回目标函数所在类的兄弟类列表
        """
        # 1. Find the related class.
        class_name, func_name = func_uri.split(".")
        if class_name not in self.brother_relation:
            return None

        return self.brother_relation[class_name]

    def class_level_retrieval(self, func_uri: str):
        """
        类级上下文检索。

        返回与目标函数存在关系的其他方法描述，例如：
            - Dependency
            - Enhancement
        """
        class_name, func_name = func_uri.split(".")
        results = []
        for info in self.func_relation:
            if info['class_name'] != class_name:
                continue
            relationships = info['relationships']
            for realtion in relationships:
                if func_name in realtion['enhanced_methods']:
                    results.append(realtion)

        if not results:
            return None

        # 最多返回两个关系（临时策略）
        return results[:2]

    def get_resource(self, func_uri: str) -> Dict[str, List[str]]:
        """
        获取与函数绑定的资源。

        当前仅支持 TestCase 资源。

        返回结构示例：
            {
                "FileWithContext": ["test_context"],
                "FileWithoutContext": ["test_context"]
            }
        """
        # Get exsitting testcases
        class_name, method_name = func_uri.split(".")
        _class = self.node_to_testcase.get(class_name)
        if _class is None:
            return None

        # 注意：method_name 可能不存在，返回 None
        return _class.get(method_name)


class PythonPropertyGraphRetrieval(PropertyGraphRetrieval):
    """
    Python 语言的 Property Graph Retrieval 实现。

    目前为占位实现，接口与基类保持一致，
    便于后续补充 Python-specific 的逻辑。
    """

    def __init__(self) -> None:
        PropertyGraphRetrieval.__init__(self)

    def pack_func_property_context(self, method_signature: MethodSignature):
        pass

    def func_level_retrieval(self, func_uri: str):
        pass

    def repo_level_retrieval(self, func_uri: str):
        """
        Python 仓库级上下文检索。

        当前行为与基类一致：
        - 返回兄弟类信息
        Return a list of brother of the given function's class.
        """
        # 1. Find the related class.
        class_name, func_name = func_uri.split(".")
        if class_name not in self.brother_relation:
            return None

        return self.brother_relation[class_name]

    def class_level_retrieval(self, func_uri: str):
        """
        Python 类级上下文检索。
        返回与目标方法存在增强 / 依赖关系的方法集合。
        Return:
            {
                "methods_involved": [
                    "query",
                    "keys_of_duplicates"
                ],
                "relationship_type": "Dependency",
                "description": "The query method records keys of duplicates when the record_duplicates flag is set, which are then accessible through the keys_of_duplicates method.",
                "enhancers": [
                    "query"
                ],
                "enhanced_methods": [
                    "keys_of_duplicates"
                ]
            },
        """
        class_name, func_name = func_uri.split(".")
        results = []
        for info in self.func_relation:
            if info['class_name'] != class_name:
                continue
            relationships = info['relationships']
            for realtion in relationships:
                if func_name in realtion['enhanced_methods']:
                    results.append(realtion)

        if not results:
            return None

        # Select at most two relationships.
        # TODO: Implement a better algorithm, such as ranking.
        return results[:2]

    def get_resource(self, func_uri: str) -> Dict[str, List[str]]:
        """
        Python 资源绑定查询。
        逻辑与基类一致，保留以支持语言定制。
        Find the resource bound to this function,
        currently only bound to Testcase
        func_uri: str, e.g. "Deduper.add"
        return:
            {
                "FileWithContext": ["test_context"],
                "FileWithoutContext": ["test_context"]
            }
        """
        # Get exsitting testcases
        class_name, method_name = func_uri.split(".")
        _class = self.node_to_testcase.get(class_name)
        if _class is None:
            return None
        # 下面这个可能会返回None
        return _class.get(method_name)


class JavaPropertyGraphRetrieval(PropertyGraphRetrieval):
    """
    Java 语言的 Property Graph Retrieval 实现。

    特点：
    - 更完整的 Context → Prompt 文本转换逻辑
    - 针对 Java TestCase / TestClass 的上下文拼装
    """

    def __init__(self) -> None:
        PropertyGraphRetrieval.__init__(self)

    def func_level_context_to_str(self, func_level_context: Context) -> str:
        """
        将函数级 Context 转换为自然语言描述字符串。
        """
        context_str = ""
        if func_level_context is not None:
            context_str += (
                f"We found the following context for the function {func_level_context.to}: \n" + \
                f"It already has the following unit tests as a reference: \n" + \
                + '<Testcase>' + self.pack_testcases_original_string(
                   get_single_value_in_dict(func_level_context.content.testcases)) + '</Testcase>\n'
            )
        return context_str

    def class_level_context_to_str(self, class_level_context: Context) -> str:
        """
        将类级 Context 转换为自然语言描述字符串。
        """
        context_str = ""
        if class_level_context is not None:
            context_str += f"We found the following context for the function {class_level_context.to} in class level:\n"
            contents: Dict[str, ContextInfo] = class_level_context.content
            for enhancer, context_info in contents.items():
                relation = context_info.relation

                context_str += (
                    f"{enhancer} and {class_level_context.to} have a {relation['relationship_type']} relationship, "
                    f"described as {relation['description']} The existing test cases for {enhancer} may provide some reference:\n" + '<Testcase>'                                                                                                                                      f"{self.pack_testcases_original_string(get_single_value_in_dict(context_info.testcases))}" + '</Testcase>\n'
                )
        return context_str

    def repo_level_context_to_str(self, repo_level_context: Context) -> str:
        """
        仓库级 Context 的字符串化接口。

        当前未实现。
        """
        context_str = ""
        if repo_level_context is not None:
            pass

        return context_str

    def context_to_str(self, func_level_context: Context, class_level_context: Context,
                       repo_level_context: Context) -> str:
        """
        将多层级 Context 统一转换为最终 Prompt 文本。
        """
        context_str = ""
        if func_level_context is not None:
            context_str += (
                f"\nWe found the following context for the function {func_level_context.to}: \n" + \
                f"It already has the following unit tests as a reference: \n" + \
                + '<Testcase>' + self.pack_testcases_original_string(
                   get_single_value_in_dict(func_level_context.content.testcases)) + '</Testcase>\n'
            )

        if class_level_context is not None:
            context_str += f"We found the following context for the function `{class_level_context.to}` in class level:\n"
            contents: Dict[str, ContextInfo] = class_level_context.content
            for enhancer, context_info in contents.items():
                relation = context_info.relation
                context_str += (
                    f"`{enhancer}` and `{class_level_context.to}` have a {relation['relationship_type']} relationship, "
                    f"described as `{relation['description']}` The existing test cases for `{enhancer}` may provide some reference:\n" + '<Testcase>\n'
                    f"{self.pack_testcases_original_string(get_single_value_in_dict(context_info.testcases))}" + '</Testcase>\n'
                )

                context_str += (
                    f"We also provide the whole class context for related testcases:\n"
                    f"{self.pack_testclass_and_imports_for_testcases(get_single_value_in_dict(context_info.testcases))}"
                )

        if repo_level_context is not None:
            pass

        return context_str

    def pack_func_property_context(self, method_signature: MethodSignature) -> Tuple[Context, Context, Context]:
        """
        根据方法签名构建完整的多层级 Context。

        注意：
        - 当前未处理同一类中方法重名的问题
        """
        file_path = method_signature.file_path
        class_name = method_signature.class_name
        method_name = method_signature.method_name

        # 函数级上下文
        # 1. Get the function level context.
        func_level_context = self.func_level_retrieval(file_path, class_name, method_name)

        # 类级上下文
        class_level_context = self.class_level_retrieval(file_path, class_name, method_name)

        # 仓库级上下文
        repo_level_context = self.repo_level_retrieval(file_path, class_name, method_name)

        return self.context_to_str(func_level_context, class_level_context, repo_level_context)
        # return func_level_context, class_level_context, repo_level_context
    def func_level_retrieval(self, file_path: str, class_name: str, method_name: str) -> Context:
        """
        Java 函数级上下文检索：
        - 查找该方法直接关联的测试用例
        """
        related_testcases = self.node_to_testcase.get(class_name, {}).get(method_name)
        if related_testcases is None:
            return None

        logger.info(f"Found {len(related_testcases)} testcases for {method_name}")
        context_info = ContextInfo(testcases=related_testcases)
        context = Context(
            _from=ContextType.function,
            to=method_name,
            content=context_info,
        )
        return context

    def class_level_retrieval(self, file_path: str, class_name: str, method_name: str) -> Context:
        """
        Java 类级上下文检索：
        - 查找与目标方法存在关系的其他方法
        - 且这些方法必须已有测试用例
        """
        """Return the function having relation with the given function in the same class 
        and having exsiting testcases"""
        # 1. First, get all the function that has relation with the given function.
        relations = []
        for _class in self.func_relation:
            if _class['class_name'] != class_name:
                continue

            for relation in _class['relationships']:
                if method_name in relation['enhanced_methods']:
                    relations.append(relation)

        # 2. For each relation, make sure that the testcase exists.
        func_to_testcase: Dict[str, ContextInfo] = {}
        for relation in relations:
            enhancers = relation['enhancers']
            for enhancer in enhancers:
                related_testcases: List[str] = self.node_to_testcase.get(class_name, {}).get(enhancer)
                if related_testcases is None:
                    continue

                context_info = ContextInfo(
                    relation=relation,
                    testcases=related_testcases
                )
                func_to_testcase[enhancer] = context_info

        if not func_to_testcase:
            return None

        context = Context(
            _from=ContextType._class,
            to=method_name,
            content=func_to_testcase
        )
        return context

    def repo_level_retrieval(self, file_path: str, class_name: str, method_name: str):
        """
        Java 仓库级上下文检索（占位实现）。
        """
        class_relation = self.brother_relation.get(class_name)
        if class_relation is None:
            return None

        # TODO: Implement repo level retrieval.


if __name__ == "__main__":
    retrieval = JavaPropertyGraphRetrieval()
    context = retrieval.pack_func_property_context(
        method_signature=...
    )
    print(context)
