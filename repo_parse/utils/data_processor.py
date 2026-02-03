"""
本模块提供了一组用于 JSON 文件与文本文件读写、元信息（metainfo）加载、
以及通用字典/代码提取辅助操作的工具函数。

主要功能包括：
1. JSON 文件的安全加载与保存（自动创建目录，异常日志记录）
2. 向 JSON 文件中追加数据（支持 list 或指定 key 的 list）
3. 加载测试用例、类、方法、包、文件依赖等元信息
4. 从结构化 JSON 中提取源码并导出为独立文件
5. 提供通用的字典辅助访问方法

所有 IO 操作均带有异常捕获，并通过 logger 进行统一日志记录，
适用于仓库解析、代码分析与自动化工具链中的基础数据处理场景。
"""

import json
import os
from typing import List

from repo_parse import logger


def add_json_item(file_path: str, item: dict, key: str = None):
    """
    向指定 JSON 文件中追加一个元素。

    - 当 key 存在时：将 item 追加到 data[key] 对应的列表中
    - 当 key 不存在时：将 JSON 视为列表并直接追加 item

    :param file_path: JSON 文件路径
    :param item: 需要追加的字典对象
    :param key: 可选的顶级 key，用于定位子列表
    """
    try:
        data = load_json(file_path)

        if key:
            # 若指定 key 不存在，则初始化为列表
            if key not in data:
                data[key] = []
            data[key].append(item)
        else:
            # 若未指定 key，则将 JSON 视为列表结构
            if not isinstance(data, list):
                data = []
            data.append(item)

        save_json(file_path, data)
    except Exception as e:
        # 捕获所有异常并记录日志，避免中断主流程
        logger.exception(f"Error adding item to json file: {e}")


def save_json(file_path: str, data: dict):
    """
    将数据保存为 JSON 文件。

    - 自动创建不存在的目录路径
    - 使用 UTF-8 编码写入

    :param file_path: JSON 文件保存路径
    :param data: 需要序列化并保存的数据
    """
    try:
        dir_path = os.path.dirname(file_path)

        # 若目录不存在则递归创建
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        logger.exception(f"Error saving json file: {e}")


def load_json(file_path: str):
    """
    从指定路径加载 JSON 文件并反序列化为 Python 对象。

    :param file_path: JSON 文件路径
    :return: 反序列化后的 Python 对象
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Error loading json file: {e}")


def load_file(file_path: str):
    """
    读取文本文件的全部内容。

    :param file_path: 文件路径
    :return: 文件内容字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.exception(f"Error loading file: {e}")


def load_testcase_metainfo(testcase_metainfo_path):
    """
    加载测试用例的元信息 JSON。

    :param testcase_metainfo_path: 测试用例元信息文件路径
    :return: 测试用例元信息数据
    """
    testcases = load_json(testcase_metainfo_path)
    return testcases


def load_class_metainfo(class_metainfo_path):
    """
    加载类定义的元信息 JSON。

    :param class_metainfo_path: 类元信息文件路径
    :return: 类元信息数据
    """
    class_metainfo = load_json(class_metainfo_path)
    return class_metainfo


def load_method_metainfo(method_metainfo_path):
    """
    加载方法/函数的元信息 JSON。

    :param method_metainfo_path: 方法元信息文件路径
    :return: 方法元信息数据
    """
    method_metainfo = load_json(method_metainfo_path)
    return method_metainfo

def load_packages_metainfo(
        packages_metainfo_path=r"/home/zhangzhe/APT/repo_parse/packages_metainfo.json"
):
    """
    加载包级别的元信息。

    :param packages_metainfo_path: 包元信息 JSON 文件路径（带默认值）
    :return: 包元信息数据
    """
    return load_json(packages_metainfo_path)


def load_file_imports_metainfo(
        file_imports_metainfo_path=r"/home/zhangzhe/APT/repo_parse/file_imports.json"
):
    """
    加载文件 import 依赖关系的元信息。

    :param file_imports_metainfo_path: 文件依赖元信息路径（带默认值）
    :return: 文件 import 元信息数据
    """
    return load_json(file_imports_metainfo_path)


def load_all_metainfo(
    class_metainfo_path: str = None,
    method_metainfo_path: str = None,
    testcase_metainfo_path: str = None,
) -> List[list]:
    """
    批量加载测试用例、类、方法的元信息，并按固定顺序返回。

    返回顺序：
    [testcases, classes, methods]

    :param class_metainfo_path: 类元信息路径
    :param method_metainfo_path: 方法元信息路径
    :param testcase_metainfo_path: 测试用例元信息路径
    :return: 包含三类元信息列表的列表
    """
    paths = [testcase_metainfo_path, class_metainfo_path, method_metainfo_path]
    keys = ['testcases', 'classes', 'methods']
    res = []

    for i, path in enumerate(paths):
        data = load_json(path)
        res.append(data[keys[i]])

    return res


def get_single_value_in_dict(dictionary):
    """
    获取字典中的第一个 value。

    常用于已知字典仅包含一个键值对的场景。

    :param dictionary: 输入字典
    :return: 字典中的第一个 value
    """
    for _, value in dictionary.items():
        return value


def get_singe_key_in_dict(dictionary):
    """
    获取字典中的第一个 key。

    :param dictionary: 输入字典
    :return: 字典中的第一个 key
    """
    return next(iter(dictionary))


def extract_code_from_json(json_file_path, output_file_path):
    """
    从 JSON 文件中提取代码字段并写入到独立文件。

    约定：
    - JSON 顶层为列表
    - 第一个元素包含 'code' 字段

    :param json_file_path: 源 JSON 文件路径
    :param output_file_path: 代码输出文件路径
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
            code = data[0]['code']

        with open(output_file_path, 'w') as out_file:
            out_file.write(code)

        logger.info(
            f"Code extracted successfully from JSON and saved to {output_file_path}"
        )
    except Exception as e:
        logger.exception(
            f"Error extracting code from JSON: json_file_path: {json_file_path}, err: {e}"
        )
