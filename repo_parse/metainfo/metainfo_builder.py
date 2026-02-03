"""
元信息构建器抽象基类模块

本模块定义了用于从解析后的元数据构建结构化对象的抽象基类。
它将原始的JSON格式元数据转换为程序化的对象模型，便于后续分析和处理。
"""

from abc import ABC, abstractmethod
import json
from typing import Dict, List

# 导入数据模型
from repo_parse.metainfo.model import Class, File, Method, TestClass, TestMethod
# 导入工具函数
from repo_parse.utils.data_processor import save_json
# 导入配置文件路径
from repo_parse.config import (
    ALL_METAINFO_PATH,  # 原始元数据JSON文件路径
    CLASS_METAINFO_PATH,  # 类元数据输出路径
    FILE_IMPORTS_PATH,  # 文件导入信息输出路径
    METHOD_METAINFO_PATH,  # 方法元数据输出路径
    PACKAGES_METAINFO_PATH,  # 包信息输出路径
    RESOLVED_METAINFO_PATH,  # 已解析元数据输出路径
    TESTCASE_METAINFO_PATH,  # 测试用例输出路径
    TESTCLASS_METAINFO_PATH,  # 测试类输出路径
)
from repo_parse import logger


class MetaInfoBuilder(ABC):
    """
    元信息构建器抽象基类

    负责将原始解析的元数据（JSON格式）转换为结构化对象模型，
    并保存到不同的输出文件中。这是元数据处理管道的核心组件。

    主要功能：
    1. 加载原始元数据JSON文件
    2. 将JSON数据转换为对象模型（方法、类、文件等）
    3. 提供保存功能，将对象序列化为JSON文件
    4. 定义构建过程的抽象接口

    属性：
        metainfo_json_path (str): 原始元数据JSON文件路径
        metainfo (List[Dict]): 加载后的元数据列表
        resolved_metainfo_path (str): 解析后元数据保存路径
        methods (List[Method]): 方法对象列表
        classes (List[Class]): 类对象列表
        testcases (List[TestMethod]): 测试方法对象列表
        testclasses (List[TestClass]): 测试类对象列表
        files (List[File]): 文件对象列表

    使用流程：
        1. 子类继承并实现 build_metainfo() 方法
        2. 在 build_metainfo() 中将原始数据转换为对象
        3. 调用 save_metainfo() 保存结果到不同文件
    """

    def __init__(self,
                 metainfo_json_path: str = ALL_METAINFO_PATH,
                 resolved_metainfo_path: str = RESOLVED_METAINFO_PATH):
        """
        初始化元信息构建器

        参数：
            metainfo_json_path (str): 原始元数据JSON文件路径，默认为配置文件中的路径
            resolved_metainfo_path (str): 解析后元数据保存路径，默认为配置文件中的路径

        初始化过程：
            1. 设置文件路径
            2. 加载原始元数据
            3. 初始化各对象列表为空
        """
        # 文件路径配置
        self.metainfo_json_path = metainfo_json_path  # 输入：原始解析数据
        self.resolved_metainfo_path = resolved_metainfo_path  # 输出：处理后数据

        # 数据存储
        self.metainfo = self.load_metainfo()  # 加载原始元数据

        # 对象列表初始化
        self.methods: List[Method] = []  # 普通方法对象列表
        self.classes: List[Class] = []  # 普通类对象列表
        self.testcases: List[TestMethod] = []  # 测试方法对象列表
        self.testclasses: List[TestClass] = []  # 测试类对象列表
        self.files: List[File] = []  # 文件对象列表

    def load_metainfo(self) -> List[Dict]:
        """
        加载原始元数据JSON文件

        从配置的路径读取已经由解析器生成的元数据文件。
        这个文件通常包含代码仓库中所有文件的结构化信息。

        返回：
            List[Dict]: 解析后的JSON数据列表，每个元素代表一个文件的元数据

        示例数据格式：
            [
                {
                    "relative_path": "src/UserService.java",
                    "original_string": "public class UserService {...}",
                    "file_hash": "abc123...",
                    "classes": [...],
                    "methods": [...],
                    ...
                },
                ...
            ]
        """
        with open(self.metainfo_json_path) as f:
            metainfo = json.load(f)  # 加载JSON数据

        return metainfo

    @abstractmethod
    def build_metainfo(self):
        pass

    def save_metainfo(self, path_to_data: Dict[str, List[Dict]]):
        """
        保存元数据到不同的文件

        将构建好的对象列表序列化为JSON并保存到指定路径。
        支持同时保存多种类型的数据到不同文件。

        参数：
            path_to_data (Dict[str, List[Dict]]): 
                路径到数据的映射字典，键为文件路径，值为对象列表

                示例：
                    {
                        METHOD_METAINFO_PATH: self.methods,
                        CLASS_METAINFO_PATH: self.classes,
                        TESTCASE_METAINFO_PATH: self.testcases,
                        ...
                    }

        处理流程：
            1. 遍历路径-数据映射字典
            2. 将每个对象列表转换为JSON格式
            3. 调用save_json保存到对应路径
            4. 记录成功日志

        注意：
            save_json函数应处理文件写入和格式化

        异常：
            IOError: 文件写入失败时可能抛出
        """

        def save_data(file_path: str, data: List):
            """
            内部辅助函数：保存单个数据列表到文件

            参数：
                file_path (str): 目标文件路径
                data (List): 要保存的对象列表
            """
            # 将对象列表转换为JSON可序列化的字典列表
            json_data = [item.to_json() for item in data]
            # 调用工具函数保存JSON文件
            save_json(file_path, json_data)

        # 遍历所有路径-数据对并保存
        for path, data in path_to_data.items():
            save_data(path, data)

        logger.info("save metainfo success!")  # 记录成功日志
