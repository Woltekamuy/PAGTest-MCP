"""
本模块提供用于生成 Java 风格标准方法签名字符串的工具函数。

生成格式示例：
[int]add(int,int)
"""

from typing import Dict, List


def get_java_standard_method_name(
    method_name: str,
    params: List[Dict[str, str]],
    return_type: str
):
    """
    输出示例：[int]add(int,int)

    :param method_name: 方法名称
    :param params: 参数列表，每个参数为包含类型信息的字典
    :param return_type: 方法返回值类型
    :return: 标准化的方法签名字符串
    """
    return f'[{return_type}]' + method_name + \
        '(' + ','.join([param['type'] for param in params]) +  ')'
