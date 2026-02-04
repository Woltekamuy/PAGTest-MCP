# ============================================================
# TestRunner
# ------------------------------------------------------------
# 本模块负责：
# 1. 执行 Maven 测试（支持指定测试类）
# 2. 调用 JaCoCo 生成并解析覆盖率结果
# 3. 按执行阶段增量保存运行状态（JSON）
#
# 作为「测试生成流水线」中的执行与反馈节点，
# 为上游 LLM 生成 / 修复逻辑提供真实的编译、运行、覆盖率信号。
# ============================================================

import os
import subprocess
import time
from typing import List

from repo_parse import logger
from repo_parse.config import JACOCO_COVERAGE_JAR_PATH, REPO_PATH, RUNNING_STATUS_DIR
from repo_parse.utils.coverage import run_jacoco_coverage_analyzer
from repo_parse.utils.data_processor import save_json


class TestRunner:
    # --------------------------------------------------------
    # 测试执行与覆盖率分析调度器
    # --------------------------------------------------------
    # 核心状态包括：
    # - 测试类名 / 目标方法
    # - Maven 执行结果
    # - JaCoCo 覆盖率结果
    # - 成功 / 失败测试文件路径集合
    # - 每次执行的增量运行状态（可追溯）

    def __init__(self, running_status_dir, exec_file_path):
        # 目标 Java 类的全限定名
        self.target_class_name = None

        # 当前测试生成/执行的唯一标识 key
        self.key = None

        # 编译后 .class 文件所在路径（供 JaCoCo 使用）
        self.class_files_path = None

        # 原始结果与 APT（自动化测试流水线）结果缓存
        self.original_result, self.apt_result = {}, {}

        # 执行失败的测试类路径集合
        self.failed_testfiles_paths = {"failed_testfiles": []}

        # 执行成功的测试类路径集合
        self.success_testfiles_paths = {"success_testfiles": []}

        # 生成的测试用例与其路径映射
        self.generated_testcase_result = {"generated_testcases": []}

        # 记录多轮生成 / 重试过程中产生的错误信息
        self.try_generated = {}

        # 运行状态文件输出目录
        self.running_status_dir = running_status_dir

        # JaCoCo 执行所需的 .exec 文件路径
        self.exec_file_path = exec_file_path

    # --------------------------------------------------------
    # 执行单个测试类的完整 APT 流程
    # --------------------------------------------------------
    # 流程：
    # 1. 执行 Maven test
    # 2. 若成功，执行 JaCoCo 覆盖率分析
    # 3. 将每个阶段的状态增量写入磁盘
    def run_apt_test(self, testclass_name: str) -> bool | List[str]:
        try:
            status = self.run_mvn_test(testclass_name=testclass_name)

            # run_mvn_test 返回非 None 表示 Maven 阶段失败
            if status is not None:
                return status, "run_mvn_test error"

        except Exception as e:
            logger.error(f"Test failed for class {testclass_name}: {e}")
            return False, "run_mvn_test unknown error"

        try:
            # ------------------------------------------------
            # 调用 JaCoCo 覆盖率分析器
            # ------------------------------------------------
            coverage_result = run_jacoco_coverage_analyzer(
                jar_path=JACOCO_COVERAGE_JAR_PATH,
                exec_file_path=self.exec_file_path,
                class_files_path=self.class_files_path,
                target_class_name=self.target_class_name,
                target_method_name=self.target_method_name.split("(")[0].split("]")[-1]
            )

            # 覆盖率获取成功时的运行状态记录
            running_status = {
                "name": testclass_name,
                "status": "coverage get success",
                "coverage_result": coverage_result,
            }
            self.incremental_save_running_status(
                file_name=testclass_name,
                data=running_status
            )

        except Exception as e:
            # 覆盖率阶段异常（如 exec 文件缺失、class 未命中等）
            logger.error(f"Failed to get coverage for class {testclass_name}: {e}")
            running_status = {
                "name": testclass_name,
                "status": "coverage get error"
            }
            self.incremental_save_running_status(
                file_name=testclass_name,
                data=running_status
            )
            return False

        logger.info(f"generated coverage_result: {coverage_result}")

        # 覆盖率为空通常意味着 JaCoCo 未命中目标方法
        if coverage_result is None:
            return False, "No coverage result found"

        return True, ""

    # --------------------------------------------------------
    # 执行 Maven test
    # --------------------------------------------------------
    # 支持：
    # - 全量测试
    # - 指定单个测试类（-Dtest=XXX）
    # 返回：
    # - None        : 执行成功
    # - List[str]   : 执行失败，返回解析后的错误信息
    def run_mvn_test(
            self,
            work_dir: str = REPO_PATH,
            testclass_name: str = None
    ) -> List[str]:
        try:
            # 切换到目标仓库目录执行 Maven
            os.chdir(work_dir)

            test_command = [
                "mvn",
                "test",
                "-Dcheckstyle.skip=true",
                "-Drat.skip=true",
                "-Dmoditect.skip=true"
            ]

            # 若指定测试类，仅运行该测试
            if testclass_name:
                test_command.extend([f"-Dtest={testclass_name}"])

            result = subprocess.run(
                test_command,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(
                f"Maven test command {' '.join(test_command)} executed successfully"
            )

            running_status = {
                "name": testclass_name,
                "status": "test success"
            }
            self.incremental_save_running_status(
                file_name=testclass_name,
                data=running_status
            )

        except subprocess.CalledProcessError as e:
            # ------------------------------------------------
            # Maven 执行失败路径
            # ------------------------------------------------
            logger.error(
                f"Maven test command failed with error code {e.returncode}: {e}"
            )
            logger.error(f"Maven test output:\n{e.stdout}")

            # 根据 Maven 输出内容对失败类型进行粗分类
            if "Unresolved compilation problem" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "compile error"
                }
            elif "org.opentest4j.AssertionFailedError:" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "assertion error"
                }
            elif "test failures" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "run error"
                }
            else:
                # 未知错误直接抛出，避免误判
                raise Exception(f"Unknown error occurred: {e}")

            self.incremental_save_running_status(
                file_name=testclass_name,
                data=running_status
            )

            # 从 Maven 输出中提取结构化错误信息
            parsed_errors = self.extract_maven_errors(
                maven_output=e.stdout
            )
            logger.info(f"Parsed Maven errors:\n{parsed_errors}")
            return parsed_errors

    # --------------------------------------------------------
    # 增量保存运行状态
    # --------------------------------------------------------
    # 设计目的：
    # - 每次执行生成独立状态文件（时间戳区分）
    # - 支持失败回溯与多轮尝试分析
    def incremental_save_running_status(self, file_name, data: dict):
        if not os.path.exists(self.running_status_dir):
            os.makedirs(self.running_status_dir)

        file_path = (
                self.running_status_dir +
                f"{file_name}_{str(int(time.time()))}.json"
        )
        save_json(file_path=file_path, data=data)
        logger.info(f"Saved running status to {file_path}")
