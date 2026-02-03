"""
属性分析器模块

该模块利用大语言模型（LLM）分析代码元素（类、方法）的属性和关系，构建智能的代码理解系统。
通过结合静态代码分析和LLM的语义理解能力，深入分析方法的关联关系、属性和上下文信息。

主要功能：
1. 使用LLM分析方法的属性和相关方法
2. 结合继承关系提供完整的类上下文
3. 缓存分析结果以提高性能
4. 支持Java语言的特定属性分析

核心类：
- PropertyAnalyzer: 属性分析器基类，继承自MetaInfo
- JavaPropertyAnalyzer: Java语言特定的属性分析器

数据流：
    目标方法 → 类上下文构建 → 静态引用解析 → LLM分析 → JSON结果 → 缓存存储
"""

import json
import os
from typing import Any, Dict, Optional

from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.llm.llm import LLM
from repo_parse.config import CLASS_METAINFO_PATH, FUNC_RELATION_PATH, METHOD_PROPERTY_DIR
from repo_parse.context_retrieval.static_retrieval.java_static_context_retrieval import JavaStaticContextRetrieval
from repo_parse.metainfo.metainfo import MetaInfo
from repo_parse.prompt.property_analyzer import Prompt
from repo_parse.utils.data_processor import load_json, save_json
from repo_parse import logger


class PropertyAnalyzer(MetaInfo):
    """
    属性分析器基类

    继承自MetaInfo，利用LLM深入分析代码方法的属性和关系。
    结合静态分析和语义理解，提供智能的代码分析方法。

    属性：
        llm (LLM): 语言模型实例，用于代码分析
        static_context_retrieval: 静态上下文检索器
        func_relation_path (str): 函数关系数据文件路径
        method_property_dir (str): 方法属性结果保存目录
        cache (Dict[Any, Any]): 分析结果缓存字典

    缓存机制：
        缓存键格式：className.methodName
        缓存文件：method_property_dir/cache.json
        缓存内容：文件路径映射，避免重复分析
    """

    def __init__(self,
                 llm: LLM = None,
                 repo_config=None,
                 static_context_retrieval=None,
                 func_relation_path: str = FUNC_RELATION_PATH):
        """
        初始化属性分析器

        参数：
            llm: 语言模型实例，用于代码分析
            repo_config: 仓库配置对象
            static_context_retrieval: 静态上下文检索器
            func_relation_path: 函数关系数据文件路径，默认为配置路径
        """
        self.llm = llm
        self.static_context_retrieval = static_context_retrieval

        # 初始化MetaInfo基类
        MetaInfo.__init__(self, repo_config=repo_config)

        # 配置路径（优先使用repo_config）
        if repo_config is not None:
            self.func_relation_path = repo_config.FUNC_RELATION_PATH
            self.method_property_dir = repo_config.METHOD_PROPERTY_DIR
        else:
            self.func_relation_path = func_relation_path
            self.method_property_dir = METHOD_PROPERTY_DIR

        self.cache = self._load_cache()  # 加载缓存

    def excute(self):
        """
        执行属性分析流程（抽象方法）

        子类需要实现具体的分析执行逻辑
        """
        pass

    def call_llm(self, system_prompt: str, user_input: str) -> str:
        """
        调用语言模型进行对话

        参数：
            system_prompt: 系统提示词，定义模型角色和任务
            user_input: 用户输入，包含具体的分析内容

        返回：
            str: LLM的完整响应文本

        注意：
            此方法委托给llm.chat()方法，具体实现取决于LLM类型
        """
        full_response = self.llm.chat(system_prompt, user_input)
        return full_response

    def extract_json(self, llm_resp: str) -> str:
        """
        从LLM响应中提取JSON内容

        处理常见的代码块格式：
        1. ```json ... ``` 格式
        2. ``` ... ``` 格式
        3. 纯JSON格式

        参数：
            llm_resp: LLM的原始响应字符串

        返回：
            str: 提取出的JSON字符串

        示例：
            输入：```json{"key": "value"}```
            输出：{"key": "value"}
        """
        if llm_resp.startswith("```json"):
            # 处理 ```json ... ``` 格式
            return llm_resp.split("```json")[1].split("```")[0]
        elif llm_resp.startswith("```"):
            # 处理 ``` ... ``` 格式
            return llm_resp.split("```")[1].split("```")[0]
        return llm_resp  # 直接返回，假定已经是JSON格式

    def extract(self, full_response: str) -> Dict:
        """
        提取并解析LLM响应中的JSON数据

        参数：
            full_response: LLM的完整响应文本

        返回：
            Dict: 解析后的JSON字典，解析失败时返回空字典

        异常处理：
            JSON解析失败时记录异常并返回空字典
        """
        resp_json: str = self.extract_json(full_response)
        try:
            resp: dict = json.loads(resp_json)
            return resp
        except Exception as e:
            logger.exception(f'Error while extract json from LLM raw output: {e}')
            return {}

    def _load_cache(self) -> Dict[Any, Any]:
        """
        从文件加载缓存数据

        缓存文件位置：method_property_dir/cache.json
        格式：{"className.methodName": "文件路径", ...}

        返回：
            Dict[Any, Any]: 缓存字典，文件不存在时返回空字典
        """
        cache_file = os.path.join(self.method_property_dir, 'cache.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_cache(self) -> None:
        """
        保存缓存数据到文件

        将内存中的缓存字典序列化为JSON格式保存到文件。
        用于持久化存储分析结果，避免重复分析。
        """
        cache_file = os.path.join(self.method_property_dir, 'cache.json')
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4, ensure_ascii=False)

    def pack_inherit_context(self, _class: Dict) -> None:
        """
        打包类的继承上下文信息

        为给定的类整合继承关系信息，包括：
        1. 继承的方法信息（从父类继承）
        2. 实现的接口信息（从接口继承）

        参数：
            _class: 类信息字典，会被更新添加original_string字段

        处理逻辑：
            1. 获取继承的方法信息并打包到类的原始字符串中
            2. 如果类实现了接口，将接口代码追加到原始字符串中
        """
        class_name = _class["name"]

        # 获取并打包继承的方法信息
        inherited_method_info = self.static_context_retrieval.get_inherited_method_info(_class=_class)
        _class['original_string'] = self.static_context_retrieval.pack_inherited_method_info(_class,
                                                                                             inherited_method_info)

        # 处理接口实现
        if _class['super_interfaces']:
            for interface_name in _class['super_interfaces']:
                interface_info = self.fuzzy_get_interface(interface_name)
                if interface_info is None:
                    continue
                # 追加接口代码到类上下文中
                _class['original_string'] += '\n Interface code: ' + interface_info['original_string'] + '\n'

    def get_related_method(self, _class: Dict, target_method: str) -> Dict:
        """
        获取与目标方法相关的方法和属性

        使用LLM分析给定类中的目标方法，识别相关的方法和属性。
        支持缓存机制避免重复分析。

        参数：
            _class: 类信息字典，包含类的详细信息
            target_method: 目标方法的签名或名称

        返回：
            Dict: 分析结果字典，包含相关方法、属性等信息

        处理流程：
            1. 检查缓存，命中则直接返回
            2. 打包类的继承上下文
            3. 构建用户输入（包括导入、类代码、包信息）
            4. 调用LLM进行分析
            5. 提取和保存结果
            6. 更新缓存

        异常处理：
            分析过程中发生异常时记录错误并返回空字典
        """
        class_name = _class["name"]
        cache_key = class_name + '.' + target_method  # 缓存键格式

        # 1. 检查缓存
        if cache_key in self.cache:
            logger.info(f"Using cached result for class: {class_name}, method: {target_method}")
            file_path = self.cache[cache_key]
            return load_json(file_path)

        try:
            # 2. 打包继承上下文
            self.pack_inherit_context(_class)

            # 3. 构建用户输入
            user_input = 'The target method is:\n' + target_method + '\n'
            original_string = 'The class is:\n' + _class["original_string"]

            # 添加导入语句
            imports = self.get_imports(file_path=_class['file_path'])
            imports_str = '\n'.join(imports)

            # 解析未解决的引用并打包包级信息
            unresolved_refs = self.static_context_retrieval.find_unresolved_refs(original_string)
            package_class_montages = self.static_context_retrieval.pack_package_info(unresolved_refs,
                                                                                     _class['file_path'],
                                                                                     original_string)
            package_class_montages_description = self.pack_package_class_montages_description(package_class_montages)

            # 组合完整的用户输入
            user_input += imports_str + original_string + package_class_montages_description

            # 4. 调用LLM进行分析
            full_response = self.call_llm(system_prompt=Prompt, user_input=user_input)

            # 5. 提取和解析结果
            resp_dict = self.extract(full_response)

            # 6. 保存结果到文件
            file_path = self.method_property_dir + '_' + class_name + '_' + target_method + '.json'
            save_json(file_path=file_path, data=resp_dict)

            # 7. 更新缓存
            self.cache[cache_key] = file_path
            self._save_cache()

        except Exception as e:
            logger.exception(f"Error in class {class_name} get_related_method: {e}")
            return {}

        logger.info("Finished resolving property")
        return resp_dict


class JavaPropertyAnalyzer(PropertyAnalyzer):
    """
    Java语言特定的属性分析器

    继承自PropertyAnalyzer，提供Java语言特定的静态上下文检索功能。
    """

    def __init__(
            self,
            repo_config=None,
            llm: LLM = None
    ):
        """
        初始化Java属性分析器

        参数：
            repo_config: 仓库配置对象
            llm: 语言模型实例，用于代码分析
        """
        # 创建Java静态上下文检索器
        static_context_retrieval = JavaStaticContextRetrieval(
            repo_config=repo_config,
        )

        # 调用父类初始化
        PropertyAnalyzer.__init__(
            self,
            llm=llm,
            repo_config=repo_config,
            static_context_retrieval=static_context_retrieval
        )