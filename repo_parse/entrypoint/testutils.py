# ============================================================
# Result Aggregation & Analysis Utilities
# ------------------------------------------------------------
# 本模块负责对测试生成与执行阶段产生的中间/最终结果进行：
# 1. 文件级扫描与聚合
# 2. 执行状态优先级归并
# 3. 覆盖率结果抽取与统计
# 4. 最终实验结果与分布报告输出
#
# 位于整个自动化测试生成流水线的「收敛与评估阶段」，
# 用于产出最终可分析、可汇报的实验结果。
# ============================================================

import os

from repo_parse.config import (
    BROTHER_ENHANCEMENTS_PATH,
    BROTHER_RELATIONS_PATH,
    CLASS_ALREADY_HAVED_TESTCASE_PATH,
    CLASS_TO_PRIMARY_TESTCASE_PATH,
    FINAL_RESULT_PATH,
    RUNNING_STATUS_DIR,
    STATUS_DISTRIBUTION_PATH,
    TARGET_METHODS_PATH,
    TESTCLASS_METAINFO_PATH,
    TESTFILES_PATH
)
from repo_parse.utils.data_processor import load_json, save_json
from repo_parse import logger


# ------------------------------------------------------------
# 查找目录下最近一次被修改的文件
# ------------------------------------------------------------
# 常用于：
# - 运行状态目录中的“最新执行结果”定位
# - 增量分析 / 断点恢复场景
def find_latest_modified_file(directory):
    if not os.path.isdir(directory):
        return None

    latest_file = None
    latest_mtime = 0

    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            mtime = os.path.getmtime(filepath)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = filepath
    return latest_file


# ------------------------------------------------------------
# 从测试类元信息中导出所有测试文件 URI
# ------------------------------------------------------------
# 主要用于：
# - 下游工具直接消费测试文件路径
# - 形成测试文件白名单
def get_testfiles():
    testclasses = load_json(TESTCLASS_METAINFO_PATH)
    testfiles = [testclass['uris'] for testclass in testclasses]
    with open(TESTFILES_PATH, 'w') as f:
        for testfile in testfiles:
            f.write(testfile + '\n')
    logger.info(f'Testfiles saved to {TESTFILES_PATH}')


# ------------------------------------------------------------
# 提取「已存在主测试用例」的类名集合
# ------------------------------------------------------------
# 输入：
# - class_to_primary_testcase.json
# 输出：
# - class_already_haved_testcase.txt
#
# 用途：
# - 约束后续测试生成范围
# - 避免对已有充分测试的类重复生成
def get_testclass_names(
    class_to_primary_testcase_path: str = CLASS_TO_PRIMARY_TESTCASE_PATH,
    class_already_haved_testcase_path: str = CLASS_ALREADY_HAVED_TESTCASE_PATH
):
    data = load_json(class_to_primary_testcase_path)
    res = []
    for k in data.keys():
        res.append(k)
    with open(class_already_haved_testcase_path, 'w') as f:
        for name in res:
            f.write(name + '\n')
    logger.info(f'get_testclass_names saved to {class_already_haved_testcase_path}')


# ------------------------------------------------------------
# 将“已有测试类”复制为“目标方法/类列表”
# ------------------------------------------------------------
# 该函数本质上是一个轻量级文件映射工具，
# 用于统一目标输入接口。
def get_target_methods():
    with open(CLASS_ALREADY_HAVED_TESTCASE_PATH, 'r') as f:
        data = f.read()
    with open(TARGET_METHODS_PATH, 'w') as f:
        f.write(data)
    logger.info(f'get_target_methods saved to {TARGET_METHODS_PATH}')


# ------------------------------------------------------------
# 加载目标方法 / 目标类列表
# ------------------------------------------------------------
# 约定：
# - 含 '.' 的行视为 method（class.method）
# - 不含 '.' 的行视为 class
#
# 返回结构：
# {
#   "class": [...],
#   "method": [...]
# }
def load_target_methods():
    if not os.path.exists(TARGET_METHODS_PATH):
        raise FileNotFoundError(f'Target methods not found at {TARGET_METHODS_PATH}')
    with open(TARGET_METHODS_PATH, 'r') as f:
        data = f.read().splitlines()
    res = {"class": [], "method": []}
    for line in data:
        if '.' in line:
            res['method'].append(line)
        else:
            res['class'].append(line)
    return res


# ------------------------------------------------------------
# 加载「已存在测试用例」的类名列表
# ------------------------------------------------------------
# 常用于：
# - 测试生成阶段的过滤条件
# - 指定类范围运行
def load_class_already_haved_testcase():
    if not os.path.exists(CLASS_ALREADY_HAVED_TESTCASE_PATH):
        raise FileNotFoundError(
            f'Class already had testcase not found at {CLASS_ALREADY_HAVED_TESTCASE_PATH}'
        )
    with open(CLASS_ALREADY_HAVED_TESTCASE_PATH, 'r') as f:
        data = f.read().splitlines()
    return data


# ------------------------------------------------------------
# 汇总最终实验结果
# ------------------------------------------------------------
# 核心逻辑：
# - 扫描 RUNNING_STATUS_DIR 中的所有状态文件
# - 按 class.method 进行聚合
# - 按预定义优先级合并多次执行状态
# - 抽取最终覆盖率结果
def extract_final_result():
    result = {}

    # --------------------------------------------------------
    # 状态优先级定义（数值越大，优先级越高）
    # --------------------------------------------------------
    # 设计目标：
    # - 覆盖率成功 > 测试成功 > 编译/断言失败
    status_priority = {
        'compile error': 0,
        'assertion error': 1,
        'test success': 2,
        'coverage_result get error': 3,
        'coverage get error': 4,
        'coverage get success': 5
    }

    for filename in os.listdir(RUNNING_STATUS_DIR):
        items = filename.split('_')
        class_name = items[0]
        method_name = items[1].split('Test')[0]

        data = load_json(os.path.join(RUNNING_STATUS_DIR, filename))
        key = class_name + '.' + method_name

        if key not in result:
            result[key] = {}
            result[key]['status'] = 'compile error'

        current_status = result[key]['status']
        new_status = data['status']

        if new_status == "generate failed":
            logger.info(f"Generate failed for {key}")

        # 根据优先级更新最终状态
        if status_priority[new_status] > status_priority[current_status]:
            result[key]['status'] = new_status

        # 覆盖率结果抽取
        if 'coverage_result' in data:
            if data['coverage_result'] is None:
                result[key]['status'] = 'coverage get error'
                continue

            if method_name in data['coverage_result']:
                coverage_result = data['coverage_result'][method_name]
                result[key]['coverage_result'] = coverage_result
            else:
                logger.error(f'Coverage result not found for {key}')
                result[key]['status'] = 'coverage get error'

    save_json(file_path=FINAL_RESULT_PATH, data=result)
    logger.info(f'Final result saved to {FINAL_RESULT_PATH}')


# ------------------------------------------------------------
# 统计分析最终结果
# ------------------------------------------------------------
# 输出：
# - 各状态数量分布
# - 行覆盖率达到 100% 的方法数量
def analyze_results(file_path: str = FINAL_RESULT_PATH):
    data = load_json(file_path)
    status_count = {}
    line_coverage_count = 0

    for key, value in data.items():
        status = value.get("status")
        if status:
            if status in status_count:
                status_count[status] += 1
            else:
                status_count[status] = 1

        coverage_result = value.get("coverage_result", [])
        if not coverage_result:
            continue

        # 约定 coverage_result 结构：
        # [Instruction, Branch, Line]
        line_coverage = coverage_result[2].get("Line Coverage")
        branch_coverage = coverage_result[1].get("Branch Coverage")

        if line_coverage == 'NaN':
            line_coverage = -1
        if branch_coverage == 'NaN':
            branch_coverage = -1

        # 统计“行覆盖率 100%”的方法数
        if line_coverage == 1.0 and (branch_coverage == 1.0 or branch_coverage == -1):
            line_coverage_count += 1

    return status_count, line_coverage_count


# ------------------------------------------------------------
# 打印并保存状态分布统计结果
# ------------------------------------------------------------
# 同时输出到：
# - stdout（便于 CLI 观察）
# - 文件（便于实验结果留档）
def print_and_save_status_distribution(
        status_count,
        line_coverage_count,
        filename=STATUS_DISTRIBUTION_PATH
):
    with open(filename, 'w') as file:
        file.write("Status Distribution:\n")
        for status, count in status_count.items():
            print(f"{status}: {count}")
            file.write(f"{status}: {count}\n")
        file.write(f"\nNumber of Line Coverage = 1: {line_coverage_count}\n")
        print(f"\nNumber of Line Coverage = 1: {line_coverage_count}")


# ------------------------------------------------------------
# CLI 入口
# ------------------------------------------------------------
# 默认行为：
# - 汇总最终结果
# - 分析并输出状态分布
if __name__ == '__main__':
    # get_testfiles()
    # get_testclass_names()

    extract_final_result()

    status_count, line_coverage_count = analyze_results()
    print_and_save_status_distribution(status_count, line_coverage_count)
