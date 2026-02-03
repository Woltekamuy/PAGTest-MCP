"""
Jacoco覆盖率分析器执行模块

该模块提供了执行Java Jacoco覆盖率分析器的功能，通过调用外部Java JAR工具
分析指定类或方法的代码覆盖率信息。支持指令覆盖率、分支覆盖率和行覆盖率三种
覆盖率指标的收集和分析。

主要功能：
1. 执行外部Java Jacoco分析工具
2. 解析覆盖率分析结果
3. 处理单个方法或整个类的覆盖率数据
4. 提供结构化的覆盖率结果输出

模块依赖：
- repo_parse.logger: 用于日志记录

"""

import subprocess
from repo_parse import logger


def run_jacoco_coverage_analyzer(jar_path, exec_file_path, class_files_path,
                                 target_class_name, target_method_name=None):
    """
    执行Jacoco覆盖率分析器并解析结果

    该函数通过调用外部的Java Jacoco分析工具，对指定的Java类或方法进行
    覆盖率分析，并返回结构化的覆盖率数据。

    参数:
    jar_path (str): Jacoco分析器JAR文件的路径
    exec_file_path (str): JaCoCo执行数据文件(.exec)的路径
    class_files_path (str): Java类文件(.class)的目录路径
    target_class_name (str): 目标Java类的全限定名
    target_method_name (str, optional): 目标方法名。如果为None，则分析整个类

    返回:
    dict: 结构化覆盖率数据。格式根据是否指定方法名而不同：
        - 指定方法名: {method_name: [instruction_cov, branch_cov, line_cov]}
        - 未指定方法名: {method1: cov_data, method2: cov_data, ...}
        其中cov_data为包含三种覆盖率指标的字典

    """
    # 转换类名格式：将包名中的 '.' 替换为路径分隔符 '/'
    if '.' in target_class_name:
        target_class_name = target_class_name.replace('.', '/')

    # 构建Java命令参数列表
    command = [
        'java', '-jar', jar_path,  # 执行Java JAR文件
        exec_file_path,  # JaCoCo执行数据文件
        class_files_path,  # 类文件目录
        target_class_name  # 目标类名
    ]

    # 如果指定了方法名，添加到命令参数中
    if target_method_name:
        command.append(target_method_name)

    try:
        # 执行外部命令
        result = subprocess.run(
            command,
            check=True,  # 检查命令执行状态
            capture_output=True,  # 捕获标准输出和错误输出
            text=True  # 以文本模式处理输出
        )

        # 记录成功执行日志
        logger.info(f"run_jacoco_coverage_analyzer Command executed successfully: {' '.join(command)}")

        # 按行分割输出结果
        output_lines = result.stdout.split('\n')

        # 处理指定方法名的覆盖率分析
        if target_method_name:
            return _parse_single_method_coverage(output_lines, target_method_name)
        # 处理整个类的覆盖率分析
        else:
            return _parse_class_coverage(output_lines)

    except subprocess.CalledProcessError as e:
        # 记录命令执行失败日志
        logger.error(f"run_jacoco_coverage_analyzer Command failed: {' '.join(command)}, {e.stdout}")
        raise  # 重新抛出异常，供上层处理


def _parse_single_method_coverage(output_lines, target_method_name):
    """
    解析单个方法的覆盖率输出结果

    参数:
    output_lines (list): JaCoCo输出的文本行列表
    target_method_name (str): 目标方法名

    返回:
    dict: 包含方法名和三种覆盖率指标的字典
    """
    # 初始化覆盖率结果字典
    instruction_coverage_result = {}
    branch_coverage_result = {}
    line_coverage_result = {}

    # 遍历输出行，解析覆盖率数据
    for line in output_lines:
        # 解析指令覆盖率
        if line.startswith('Instruction Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)

            # 处理重复方法名的情况（取最大值）
            if "Instruction Coverage" in instruction_coverage_result:
                instruction_coverage_result["Instruction Coverage"] = max(
                    instruction_coverage_result["Instruction Coverage"],
                    cov_percentage
                )
                logger.warning(f"Duplicate method name found: {target_method_name}")
            else:
                instruction_coverage_result["Instruction Coverage"] = cov_percentage

        # 解析分支覆盖率
        elif line.startswith('Branch Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)

            # 处理重复方法名的情况（取最大值）
            if "Branch Coverage" in branch_coverage_result:
                branch_coverage_result["Branch Coverage"] = max(
                    branch_coverage_result["Branch Coverage"],
                    cov_percentage
                )
            else:
                branch_coverage_result["Branch Coverage"] = cov_percentage

        # 解析行覆盖率
        elif line.startswith('Line Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)

            # 处理重复方法名的情况（取最大值）
            if "Line Coverage" in line_coverage_result:
                line_coverage_result["Line Coverage"] = max(
                    line_coverage_result["Line Coverage"],
                    cov_percentage
                )
            else:
                line_coverage_result["Line Coverage"] = cov_percentage

    # 返回结构化结果
    return {
        target_method_name: [
            instruction_coverage_result,
            branch_coverage_result,
            line_coverage_result
        ]
    }


def _parse_class_coverage(output_lines):
    """
    解析整个类的覆盖率输出结果

    参数:
    output_lines (list): JaCoCo输出的文本行列表

    返回:
    dict: 包含类中所有方法覆盖率数据的字典
    """
    methods_coverage = {}  # 存储所有方法的覆盖率数据
    current_method = None  # 当前正在处理的方法名
    current_coverage = {}  # 当前方法的覆盖率数据

    # 遍历输出行，按方法分组解析覆盖率数据
    for line in output_lines:
        # 新的方法开始
        if line.startswith('Method name:'):
            # 保存上一个方法的数据
            if current_method:
                methods_coverage[current_method] = current_coverage

            # 开始处理新方法
            current_method = line.split(':')[-1].strip()
            current_coverage = {}

        # 解析指令覆盖率
        elif line.startswith('Instruction Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)
            current_coverage['Instruction Coverage'] = cov_percentage

        # 解析分支覆盖率
        elif line.startswith('Branch Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)
            current_coverage['Branch Coverage'] = cov_percentage

        # 解析行覆盖率
        elif line.startswith('Line Coverage:'):
            cov_percentage = _parse_coverage_percentage(line)
            current_coverage['Line Coverage'] = cov_percentage

    # 保存最后一个方法的数据
    if current_method:
        methods_coverage[current_method] = current_coverage

    return methods_coverage


def _parse_coverage_percentage(coverage_line):
    """
    解析覆盖率百分比字符串

    将字符串形式的覆盖率百分比转换为浮点数，
    处理特殊的 'NaN' 值情况。

    参数:
    coverage_line (str): 包含覆盖率信息的行

    返回:
    float: 覆盖率百分比值，NaN转换为-1
    """
    # 提取百分比值并去除空白字符
    cov_percentage = coverage_line.split(':')[-1].strip()

    # 处理NaN（Not a Number）情况
    if cov_percentage == 'NaN':
        return -1.0  # 使用-1表示无效的覆盖率值

    return float(cov_percentage)