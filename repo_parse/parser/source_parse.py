"""
2. 使用LanguageParser解析代码仓库中的源代码文件，提取元数据

本模块是代码仓库解析系统的核心处理模块，负责批量处理整个代码仓库中的源文件，
提取结构化信息，并生成统一的元数据表示。
产物为 all_metainfo.json 文件，包含所有源文件的解析结果。
"""

import os
from source_parser.parsers.language_parser import LanguageParser

from repo_parse.common.enum_types import LanguageEnum
from source_parser.utils import static_hash
from repo_parse.utils.data_processor import save_json
from repo_parse.config import EXCEPTE_PATH, REPO_PATH, ALL_METAINFO_PATH
from repo_parse import logger


class Processer:
    """
    源代码文件批量处理器

    负责批量处理指定目录下的所有源文件，使用指定的语言解析器提取结构化信息，
    并将结果保存为统一的元数据格式。

    属性：
        repo_dir (str): 代码仓库根目录路径
        language (LanguageEnum): 源代码语言枚举值
        parser (LanguageParser): 语言解析器实例
    """

    def __init__(self,
                 repo_dir: str,
                 language: LanguageEnum,
                 parser: LanguageParser):
        """
        初始化处理器

        参数：
            repo_dir (str): 代码仓库目录路径
            language (LanguageEnum): 编程语言类型枚举
            parser (LanguageParser): 语言解析器实例
        """
        self.repo_dir = repo_dir
        self.language = language
        self.parser = parser

    def batch_process(self, directory: str) -> list:
        """
        批量处理目录下的所有源文件

        遍历指定目录及其子目录，对每个符合条件的源文件：
        1. 读取文件内容
        2. 使用解析器预处理和解析
        3. 提取结构化元数据
        4. 组装结果

        参数：
            directory (str): 要处理的目录绝对路径

        返回：
            list: 处理结果列表，每个元素是一个文件的元数据字典

        处理流程：
            1. 遍历目录树，过滤隐藏目录和排除路径
            2. 识别特定语言的文件扩展名
            3. 逐个文件读取和解析
            4. 收集和组装元数据
            5. 返回所有文件的处理结果
        """
        results = []  # 存储所有文件的处理结果
        parser = self.parser

        # 文件后缀过滤：目前只支持Java
        # TODO: 未来可扩展支持多种语言
        file_suffix = "java"

        # 使用os.walk递归遍历目录树
        for root, dirs, files in os.walk(directory):
            root_abs = os.path.abspath(root)  # 当前目录的绝对路径

            # 过滤隐藏目录：跳过以.开头的目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            # 过滤排除路径：跳过配置文件中指定的不需要处理的目录
            # EXCEPTE_PATH示例：["/path/to/exclude", ...]
            new_dirs = []
            for d in dirs:
                dir_full_path = os.path.join(root_abs, d)
                if dir_full_path not in EXCEPTE_PATH:
                    new_dirs.append(d)
            dirs[:] = new_dirs  # 原地修改dirs列表，控制os.walk的遍历行为

            # 处理当前目录下的所有文件
            for file in files:
                # 跳过非目标语言文件
                if not file.endswith(file_suffix):
                    continue

                file_path = os.path.join(root, file)  # 文件绝对路径
                relative_path = os.path.relpath(file_path, directory)  # 相对于仓库根目录的路径

                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_contents = f.read()

                try:
                    # 预处理文件内容：可能包括清理、标准化等操作
                    processed_contents = parser.preprocess_file(file_contents)

                    # 更新解析器状态：准备解析当前文件
                    parser.update(processed_contents)

                    # 跳过空文件或预处理后为空的内容
                    if not processed_contents:
                        continue

                except Exception as e_err:
                    # 捕获预处理过程中的异常，记录日志并跳过该文件
                    logger.exception(f"\n\tFile {file_path} raised {type(e_err)}: {e_err}\n")
                    continue

                # 解析文件，获取结构化schema
                # schema包含类、方法、字段等结构信息
                schema = parser.schema

                # 跳过没有提取到任何特征的文件
                if not any(schema.values()):
                    continue

                # 组装文件处理结果
                file_results = {
                    "relative_path": relative_path,  # 文件相对路径
                    "original_string": processed_contents,  # 预处理后的源代码
                    "file_hash": static_hash(file_contents),  # 文件内容哈希值（必需！用于唯一标识）
                }

                # 合并解析器提取的schema信息
                file_results.update(schema)

                # 添加到结果列表
                results.append(file_results)

        # 记录处理统计信息
        logger.info(f"{len(results)} files processed")
        return results


def run_source_parse(repo_path: str, language: LanguageEnum, parser: LanguageParser):
    """
    执行源代码解析的主函数

    这是模块的主要入口点，负责：
    1. 创建处理器实例
    2. 批量处理整个仓库
    3. 保存解析结果到JSON文件

    参数：
        repo_path (str): 代码仓库路径
        language (LanguageEnum): 编程语言类型
        parser (LanguageParser): 语言解析器实例

    工作流程：
        1. 初始化处理器
        2. 批量处理仓库中的所有源文件
        3. 将结果保存到配置的路径
        4. 记录完成日志

    注意：
        - 该函数会修改全局配置的ALL_METAINFO_PATH文件
        - 需要有写入权限
    """
    logger.info("start repo parsing...")

    # 创建处理器实例
    processer = Processer(repo_dir=repo_path, language=language, parser=parser)

    # 执行批量处理
    results = processer.batch_process(repo_path)

    # 保存结果到JSON文件
    # ALL_METAINFO_PATH是配置文件指定的输出路径
    save_json(ALL_METAINFO_PATH, results)

    logger.info("repo parsed successfully!")


#if __name__ == "__main__":
    # file_path = r"/home/zhangzhe/fuzzing-repo/source_parser/source_parser/parsers/python_parser.py"
    # schema = process_python_file(file_path)
    # print(schema)

    # repo_path = REPO_PATH
    # processor = Processor(repo_dir=repo_path, language=LanguageEnum.JAVA, parser=RefineJavaParser())
    # results = processer.batch_process(repo_path)
    #-------------------
    """
    repo_path = r"C:\\Users\v-zhanzhe\Desktop\code2\redka-main\redka-main"
    processer = Processer(repo_dir=repo_path, language=LanguageEnum.GO, parser=RefineGoParser())
    results = processer.batch_process(repo_path)
    save_json(ALL_METAINFO_PATH, results)
    """