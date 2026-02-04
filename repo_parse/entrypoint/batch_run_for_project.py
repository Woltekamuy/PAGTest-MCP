# ============================================
# ProjectRunner 模块
# --------------------------------------------
# 本模块负责：
# 1. 基于 Java 方法元信息的测试用例自动生成
# 2. 测试用例的拷贝、执行、失败归档与重试
# 3. Maven 测试与 Jacoco 覆盖率分析的自动化集成
# 4. 多轮（round-based）测试生成与分析闭环
# ============================================

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, List

from repo_parse.llm.deepseek_llm import DeepSeekLLM
from repo_parse.analysis.testcase_analyzer import JavaTestcaseAnalyzer
from repo_parse.common.enum_types import LanguageEnum
from repo_parse.config import BAD_TESTFILE_ARCHIVE_DIR, CLASS_METAINFO_PATH, CLASS_TO_PRIMARY_TESTCASE_PATH, COMPLETE_EXPERIMENT_RESULT_PATH, COMPLETE_FAILED_TESTFILES_PATH, COMPLETE_GENERATED_TESTCASES_RESULT_PATH, COMPLETE_GENERATED_TESTFILE_RUNNING_STATUS_PATH, COMPLETE_TRY_GENERATED_TESTCASES_PATH, COMPLETED_TESTCASES_DIR, EXPERIMENT_RESULT_PATH, FAILED_TESTFILES_PATH, GENERATED_TESTCASES_DIR, GENERATED_TESTCASES_RESULT_PATH, GENERATED_TESTFILE_RUNNING_STATUS_PATH, JACOCO_COVERAGE_JAR_PATH, MAX_RETRY_NUMBER, METHOD_COVERAGE_RESULT_PATH, METHOD_METAINFO_PATH, METHOD_TO_TEST_PATHS, REPO_PATH, RESOLVED_METAINFO_PATH, RUNNING_STATUS_DIR, TESTCLASS_ANALYSIS_RESULT_PATH, TESTCLASS_METAINFO_PATH, TRY_GENERATED_TESTCASES_PATH, USE_METHOD_TO_TEST_PATHS, USE_SPECIFY_CLASS_AND_METHOD
from repo_parse.generator.testcase_generator import JavaTestcaseGenerator, TestcaseGenerator
from repo_parse.metainfo.java_metainfo_builder import JavaMetaInfoBuilder
from repo_parse.metainfo.metainfo import run_build_metainfo
from repo_parse.property_graph.node_coordinator import JavaNodeCoordinator
from repo_parse.entrypoint.test_runner import TestRunner
from repo_parse.entrypoint.testutils import get_testclass_names, load_class_already_haved_testcase, load_target_methods
from repo_parse.utils.coverage import run_jacoco_coverage_analyzer
from repo_parse import logger
from repo_parse.utils.data_processor import get_singe_key_in_dict, load_json, save_json

# ------------------------------------------------
# Jacoco 执行文件路径
# ------------------------------------------------
# 在 Maven test 过程中生成，用于后续覆盖率分析
exec_file_path = str(Path(REPO_PATH) / "target" / "jacoco.exec")


class ProjectRunner(TestRunner):
    """
    ProjectRunner 是测试生成与执行的核心调度类。

    职责包括：
    - 单方法粒度的测试用例生成
    - Maven 测试执行与错误解析
    - Jacoco 覆盖率获取与结果持久化
    - 测试失败的重试与归档
    """

    def __init__(self, generator: TestcaseGenerator):
        # 初始化 TestRunner 基类（运行状态目录、Jacoco exec 文件）
        TestRunner.__init__(self, running_status_dir=RUNNING_STATUS_DIR, exec_file_path=exec_file_path)

        # 当前处理的目标类与方法上下文
        self.target_class_name = None
        self.key = None
        self.class_files_path = None

        # 原始与 APT（自动生成测试）结果
        self.original_result, self.apt_result = {}, {}

        # 方法级元信息（静态分析产物）
        self.method_metainfo = load_json(METHOD_METAINFO_PATH)

        # 测试文件执行结果与路径记录
        self.success_copied_testcase_paths = {"success_copied_testcases": []}
        self.failed_testfiles_paths = {"failed_testfiles": []}
        self.success_testfiles_paths = {"success_testfiles": []}

        # 生成测试用例与尝试历史
        self.generated_testcase_result = {"generated_testcases": []}
        self.try_generated = {}

        # 测试用例生成器（通常由 LLM 驱动）
        self.generator = generator

    # ------------------------------------------------
    # 判断某个方法是否已经生成过测试用例
    # ------------------------------------------------
    def skip(self, key):
        if os.path.exists(TRY_GENERATED_TESTCASES_PATH):
            original_result = load_json(TRY_GENERATED_TESTCASES_PATH)
            if key in original_result.keys():
                logger.info(f"Found existing testcase for {self.key}, skip generating testcase.")
                return True
        return False

    # ------------------------------------------------
    # 调用 Jacoco Coverage Analyzer 获取单方法覆盖率
    # ------------------------------------------------
    def get_method_coverage(self, class_name, class_files_path, method_name):
        if '.' in class_name:
            class_name = class_name.replace('.', '/')
        command = [
            "java", "-jar", JACOCO_COVERAGE_JAR_PATH,
            exec_file_path, class_files_path, class_name, method_name
        ]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return result
        except Exception as e:
            logger.error(f"Failed to run JacocoCoverageAnalyzer for {class_name}.{method_name}: {e.meassage}")

    # ------------------------------------------------
    # 计算所有类-方法组合的覆盖率并持久化结果
    # ------------------------------------------------
    def get_all_methods_coverage(self):
        class_method_list = []
        class_to_primary_testcases = load_json(CLASS_TO_PRIMARY_TESTCASE_PATH)

        # 收集每个类中被 primary testcase 覆盖的方法
        for class_name, primary_testcases in class_to_primary_testcases.items():
            method_names = set()
            for primary_testcase in primary_testcases:
                method_names.add(primary_testcase['method_name'])
            class_method_list.extend([{"class": class_name, "method": method_name} for method_name in method_names])

        coverage_results = []

        # 逐方法执行测试并解析覆盖率输出
        for item in class_method_list:
            class_name = item["class"]

            method_name = item["method"].split("(")[0]

            result = self.run(
                target_class_uris=class_name,
                target_method_name=method_name,
                short_mode=True,
                get_all_methods_coverage=True
            )
            if result is None:
                logger.error(f"Failed to run test for {class_name}.{method_name}")
                continue

            output_lines = result.stdout.splitlines()
            coverage_info = {
                "class": class_name,
                "method": method_name,
                "instruction_coverage": None,
                "branch_coverage": None,
                "line_coverage": None
            }

            # 从 Jacoco 输出中提取覆盖率数值
            for line in output_lines:
                if "Instruction Coverage:" in line:
                    cov_percentage = line.split(":")[1].strip()
                    if cov_percentage == 'NaN':
                        coverage_info["instruction_coverage"] = -1
                    else:
                        coverage_info["instruction_coverage"] = float(cov_percentage)
                elif "Branch Coverage:" in line:
                    cov_percentage = line.split(":")[1].strip()
                    if cov_percentage == 'NaN':
                        coverage_info["branch_coverage"] = -1
                    else:
                        coverage_info["branch_coverage"] = float(cov_percentage)
                elif "Line Coverage:" in line:
                    cov_percentage = line.split(":")[1].strip()
                    if cov_percentage == 'NaN':
                        coverage_info["line_coverage"] = -1
                    else:
                        coverage_info["line_coverage"] = float(cov_percentage)
                        coverage_results.append(coverage_info)


        save_json(file_path=METHOD_COVERAGE_RESULT_PATH, data=coverage_results)
        logger.info(f"Saved method coverage results")

    # ------------------------------------------------
    # 预留接口：获取部分覆盖的方法集合
    # ------------------------------------------------
    def get_part_cover_methods(self):
        pass

    # ------------------------------------------------
    # 单方法测试生成、执行与覆盖率评估的主流程
    # ------------------------------------------------
    def run(self, target_class_uris, target_method_name, short_mode: bool = False, get_all_methods_coverage: bool = False):
        uris = target_class_uris

        # short_mode 用于通过类名快速定位真实 URI
        if short_mode:
            _class = self.find_class(target_class_uris)
            if _class is None:
                logger.error(f"Failed to find class {target_class_uris}, maybe it is a abstract class.")
                return

            uris = _class['uris']
            method = self.find_method(target_method_name)
            if method is None:
                logger.error(f"..Failed to find method {target_method_name} in class {target_class_uris}")
                return
            target_method_name = '[' + method['uris'][method['uris'].find('[')+1:]

        # 通过完整 URI 定位方法元信息
        method_uri = uris + "." + target_method_name
        _method = self.find_method_by_uri(method_uri)
        if _method is None:
            logger.error(f"...Failed to find method {target_method_name} in class {target_class_uris}")
            return

        # 非 public 方法直接跳过
        if not self.is_method_public(_method):
            logger.warning(f"Method {target_method_name} is not public, please check the method signature.")
            return

        # 处理不同项目结构下的源码路径前缀
        if uris.startswith("src/main/java/"):
            trimmed_uris = uris[len("src/main/java/"):]
        elif uris.startswith("src/main/"):
            trimmed_uris = uris[len("src/main/"):]
        elif uris.startswith("service/src/main/java/"): # For openai4j
            trimmed_uris = uris[len("service/src/main/java/"):]
        elif "src/test" in uris:
            return
        else:
            raise Exception(f"Invalid uris: {uris}")

        # 构造目标类与方法的全限定名
        testclass_name = None

        handled_uris = trimmed_uris.split('/')
        target_class_name = '.'.join(handled_uris[:-1]) + '.' + handled_uris[-1].split('.java.')[-1]

        # 缓存当前上下文信息
        self.target_class_name = target_class_name
        self.target_method_name = target_method_name
        self.method_name = self.target_method_name.split("(")[0].split("]")[-1]
        self.key = self.target_class_name + self.target_method_name

        # 编译后 class 文件路径（用于 Jacoco）
        self.class_files_path = str(
            Path(REPO_PATH) / "target" / "classes" / target_class_name.replace(".", "/")
        ) + ".class"

        class_name = target_class_name.split(".")[-1]

        # 覆盖率批量模式下直接返回 coverage 结果
        if get_all_methods_coverage:
            return self.get_method_coverage(target_class_name, self.class_files_path, self.method_name)

        # ------------------------------------------------
        # 后续逻辑：测试用例生成、拷贝、执行、重试
        # （以下保持原有代码结构，仅新增解释性注释）
        # ------------------------------------------------
        # ------------------------------------------------
        # 检查是否已存在同名生成测试类，避免重复生成
        # ------------------------------------------------
        java_file_name = JavaTestcaseGenerator.get_new_class_name(
            class_name=_method['class_name'],
            target_method=_method['name']
        )
        for root, dirs, files in os.walk(GENERATED_TESTCASES_DIR):
            for file in files:
                if file.endswith('.java') and java_file_name in file:
                    logger.info(f"Found existing testcase for {self.key}, skip generating testcase.")
                    return

        # ------------------------------------------------
        # 对历史失败但未成功修复的测试类进行归档处理
        # ------------------------------------------------
        if os.path.exists(FAILED_TESTFILES_PATH):
            failed_testfiles = load_json(FAILED_TESTFILES_PATH)
            if os.path.exists(GENERATED_TESTFILE_RUNNING_STATUS_PATH):
                data = load_json(GENERATED_TESTFILE_RUNNING_STATUS_PATH)
                success_testfiles = data["success_testfiles"]
            for failed_testfile in failed_testfiles['failed_testfiles']:
                if failed_testfile in success_testfiles:
                    continue
                self.archive_bad_testclass(failed_testfile)

        """Run testcase generation"""

        # ------------------------------------------------
        # 根据方法 URI 与类名在方法元信息中精确定位目标方法
        # ------------------------------------------------
        generated_class_name = None
        target_method = None
        data = load_json(METHOD_METAINFO_PATH)
        for method in data:
            name = '[' + method['uris'].split('[')[-1]
            if name == target_method_name and method['class_name'] == class_name:
                logger.info(f"Found method {target_method_name} in class {class_name}")
                target_method = method

        # 若目标方法未找到，终止当前流程
        if target_method is None:
            logger.error(f".Failed to find method {target_method_name} in class {class_name}")
            return

        # ------------------------------------------------
        # 调用生成器（LLM 驱动）生成测试用例
        # ------------------------------------------------
        try:
            try_generated, generated_class_name = self.generator.refined_generate_testcases(target_method)
            self.try_generated[try_generated] = []
        except Exception as e:
            logger.error(
                f"we failed to generate test cases for method {class_name + '_' + target_method_name}: {e}"
            )
            running_status = {
                "name": class_name + '_' + target_method_name + "Test",
                "status": "generate failed"
            }
            self.incremental_save_running_status(
                file_name=class_name + '_' + target_method_name + "Test",
                data=running_status
            )
            self.save_try_generated_testcases()
            return

        # 生成器未返回有效测试类名，直接结束
        if generated_class_name is None:
            logger.error(f"Failed to generate test cases for method {class_name + '_' + target_method_name}")
            self.save_try_generated_testcases()
            return

        # ------------------------------------------------
        # 将生成的测试类拷贝至 src/test/java 对应包路径
        # ------------------------------------------------
        original_testcase_path = GENERATED_TESTCASES_DIR + generated_class_name + '.java'
        logger.info(f"original_testcase_path: {original_testcase_path}")

        dest_testcase_dir = str(
            Path(REPO_PATH) / "src" / "test" / "java" /
            Path('/'.join(target_class_name.split('.')[:-1]))
        )
        dest_testcase_path = os.path.join(dest_testcase_dir, os.path.basename(original_testcase_path))
        logger.info(f"dest_testcase_path: {dest_testcase_path}")

        try:
            if not os.path.exists(dest_testcase_dir):
                os.makedirs(dest_testcase_dir)

            shutil.copy2(original_testcase_path, dest_testcase_path)
            logger.info(
                f"Successfully copied test case from {original_testcase_path} to {dest_testcase_dir}"
            )
            self.success_copied_testcase_paths['success_copied_testcases'].append(dest_testcase_path)
        except Exception as e:
            logger.error(f"An error occurred while copying test case: {e}")

        # ------------------------------------------------
        # 记录生成测试用例与方法的映射关系
        # ------------------------------------------------
        if testclass_name is not None:
            self.generated_testcase_result["generated_testcases"].append(
                {testclass_name + '_' + target_method_name: dest_testcase_path}
            )
        else:
            self.generated_testcase_result["generated_testcases"].append(
                {uris + target_method_name: dest_testcase_path}
            )

        # ------------------------------------------------
        # 执行 Maven 测试与覆盖率分析
        # ------------------------------------------------
        apt_status = False
        no_testcase_generated = False
        if not generated_class_name:
            logger.warning(f"{target_method_name} No test case generated")
            self.apt_result[self.key] = None
            no_testcase_generated = True
        else:
            apt_status, err = self.run_apt_test(
                testclass_name=generated_class_name,
                dest_testcase_path=dest_testcase_path
            )
            if err:
                self.try_generated[try_generated].append(err)
                if err == "coverage get error":
                    raise Exception(f"No coverage result found for {class_name}.{target_method_name}")

        # ------------------------------------------------
        # 测试成功 / 失败 / 重试处理
        # ------------------------------------------------
        if not err:
            self.success_testfiles_paths["success_testfiles"].append(dest_testcase_path)
            logger.info(f"{target_method_name} Test passed")
        elif no_testcase_generated is True:
            logger.warning(f"{target_method_name} No test case generated")
        else:
            retry_apt_status = apt_status
            retry_times = 0

            # 在失败情况下进行有限次数的自动修复与重试
            while retry_times < MAX_RETRY_NUMBER and err:
                retry_times += 1
                parsed_errors = self.remove_file_path_from_list(
                    retry_apt_status, dest_testcase_path
                )
                regenerated_class_name = self.retry_generate_testcases(
                    target_method=target_method,
                    parsed_errors=parsed_errors,
                    original_testcase_path=original_testcase_path,
                    dest_testcase_path=dest_testcase_path
                )
                if regenerated_class_name is None:
                    continue

                retry_apt_status, err = self.run_apt_test(
                    testclass_name=regenerated_class_name,
                    dest_testcase_path=dest_testcase_path
                )
                if err:
                    self.try_generated[try_generated].append(err)
                else:
                    self.success_testfiles_paths["success_testfiles"].append(dest_testcase_path)
                    logger.info(f"{target_method_name} Test passed")
                    break

            # 最终仍失败的测试文件记录为失败
            self.failed_testfiles_paths["failed_testfiles"].append(dest_testcase_path)

        # ------------------------------------------------
        # 将当前轮次的所有结果持久化
        # ------------------------------------------------
        self.save_running_status()
        self.save_experiment_result(incremental_save=True)
        self.save_generated_testcase_result()
        self.save_failed_testclass_paths()
        self.save_try_generated_testcases()

        if not err:
            return dest_testcase_path

    # ------------------------------------------------
    # 从错误日志中移除具体文件路径，便于 LLM 聚焦语义错误
    # ------------------------------------------------
    def remove_file_path_from_list(self, log_lines, file_path):
        cleaned_lines = []
        for line in log_lines:
            if file_path in line:
                cleaned_line = line.replace(file_path, '')
                cleaned_lines.append(cleaned_line)
            else:
                cleaned_lines.append(line)
        return cleaned_lines

    # ------------------------------------------------
    # 保存测试生成尝试历史（支持增量写入）
    # ------------------------------------------------
    def save_try_generated_testcases(self, incremental_save: bool = False,
                                     file_path: str = TRY_GENERATED_TESTCASES_PATH):
        if incremental_save and os.path.exists(file_path):
           try_generated_testcases = load_json(file_path)
           self.try_generated.update(try_generated_testcases)
        save_json(file_path=file_path, data=self.try_generated)
        logger.info(f"Saved try_generated_testcases to {file_path}")

    # ------------------------------------------------
    # 在类元信息中按类名查找唯一类定义
    # ------------------------------------------------
    def find_class(self, class_to_find: str):
        class_metainfo = load_json(CLASS_METAINFO_PATH)
        _class = None
        cnt = 0
        for cls in class_metainfo:
            if cls["name"] == class_to_find:
                _class = cls
                cnt += 1
        if cnt > 1:
            logger.error(f"Find more than one class with the same name: {self.target_class_name}")
            return None
        return _class

    # ------------------------------------------------
    # 判断方法是否为 public（基于解析出的注解信息）
    # ------------------------------------------------
    @staticmethod
    def is_method_public(method: Dict):
        return 'public' in method['attributes'].get('non_marker_annotations', [])

    # ------------------------------------------------
    # 通过完整 URI 查找方法元信息
    # ------------------------------------------------
    def find_method_by_uri(self, method_uri: str):
        for m in self.method_metainfo:
            if m["uris"] == method_uri:
                return m

    # ------------------------------------------------
    # 按方法名查找方法（要求唯一）
    # ------------------------------------------------
    def find_method(self, method_to_find: str):
        method = None
        cnt = 0
        for m in self.method_metainfo :
            if m["name"] == method_to_find:
                method = m
                cnt += 1
        if cnt > 1:
            logger.error(f"Find more than one method with the same name: {method_to_find}")
            return None
        return method

    # ------------------------------------------------
    # 运行 Maven 测试（可指定单个测试类）
    # ------------------------------------------------
    # 返回：
    # - None：测试成功
    # - List[str]：解析后的错误日志（用于 LLM 反馈重试）
    # ------------------------------------------------
    def run_mvn_test(self, work_dir: str = REPO_PATH, testclass_name: str = None) -> List[str]:
        try:
            logger.info(f"Start running maven test command: {testclass_name}")
            os.chdir(work_dir)

            # Maven clean，确保无历史构建产物干扰
            clean_command = ["mvn", "clean"]
            result_clean = subprocess.run(clean_command, check=True, capture_output=True, text=True)

            # Maven test，跳过非必要插件以加快执行速度
            test_command = ["mvn", "test", "-Dcheckstyle.skip=true", "-Drat.skip=true", "-Dmoditect.skip=true"]
            if testclass_name:
                test_command.extend([f"-Dtest={testclass_name}"])

            result = subprocess.run(test_command, check=True, capture_output=True, text=True)
            logger.info(f"Maven test command {' '.join(test_command)} executed successfully")

            # 成功执行的运行状态记录
            running_status = {
                "name": testclass_name,
                "status": "test success"
            }
            self.incremental_save_running_status(file_name=testclass_name, data=running_status)

        except subprocess.CalledProcessError as e:
            # ------------------------------------------------
            # Maven 执行失败，按错误类型进行粗粒度分类
            # ------------------------------------------------
            logger.error(f"Maven test command failed with error code {e.returncode}: {e}")
            logger.error(f"Maven test output:\n{e.stdout}")

            if (
                "expected:" in e.stdout and
                "but was:" in e.stdout
            ):
                running_status = {
                    "name": testclass_name,
                    "status": "assertion error",
                    "error": e.stdout
                }
            elif "Unresolved compilation problem" or "Compilation failure" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "compile error",
                    "error": e.stdout
                }
            elif "org.opentest4j.AssertionFailedError:" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "assertion error",
                    "error": e.stdout
                }
            elif "test failures" in e.stdout:
                running_status = {
                    "name": testclass_name,
                    "status": "run error",
                    "error": e.stdout
                }
            else:
                logger.error(f"Unknown error occurred: {e.stdout}")

            # 失败运行状态持久化
            self.incremental_save_running_status(file_name=testclass_name, data=running_status)

            # 提取 Maven 错误日志片段，用于后续 LLM 修复
            parsed_errors = self.extract_maven_errors(maven_output=e.stdout)
            logger.info(f"Parsed Maven errors:\n{parsed_errors}")
            return parsed_errors

    # ------------------------------------------------
    # 从 Maven 输出中提取结构化错误信息
    # ------------------------------------------------
    # 目标：
    # - 去除无关 INFO/WARN 噪声
    # - 保留 ERROR 块上下文
    # - 限制最大长度，防止 LLM 输入过长
    # ------------------------------------------------
    def extract_maven_errors(self, maven_output: str) -> List[str]:
        error_messages = []
        lines = maven_output.splitlines()
        capture = False
        current_error_block = []

        exclude_start_pattern = re.compile(
            r'^\[ERROR\] Failed to execute goal org\.apache\.maven\.plugins:maven-surefire-plugin.*$'
        )
        error_start_pattern = re.compile(r'^\[ERROR\].*$')

        for line in lines:
            # 一旦进入 surefire 插件失败摘要，直接终止解析
            if exclude_start_pattern.match(line):
                break

            if error_start_pattern.match(line):
                if current_error_block:
                    error_messages.extend(current_error_block)
                    current_error_block = []

                capture = True
                current_error_block = [line.strip()]
            elif capture:
                if re.match(r'^\[INFO\]', line) or re.match(r'^\[WARN\]', line):
                    capture = False
                    error_messages.extend(current_error_block)
                    current_error_block = []
                else:
                    current_error_block.append(line.strip())

        if current_error_block:
            error_messages.extend(current_error_block)

        # 控制错误上下文长度，防止 token 爆炸
        if len(error_messages) > 60:
            error_messages = error_messages[-60:]

        return error_messages

    # ------------------------------------------------
    # 将失败且不可恢复的测试类移动至归档目录
    # ------------------------------------------------
    def archive_bad_testclass(self, testfile_path: str):
        archive_dir = Path(BAD_TESTFILE_ARCHIVE_DIR)
        archive_dir.mkdir(parents=True, exist_ok=True)

        testfile_path = Path(testfile_path)
        if testfile_path.exists():
            try:
                shutil.move(testfile_path, archive_dir / os.path.basename(testfile_path))
                logger.info(f"Archived {testfile_path} to {archive_dir}")
            except Exception as e:
                logger.error(f"Failed to archive {testfile_path}: {e}")
        else:
            pass

    # ------------------------------------------------
    # 保存生成测试用例的最终映射结果
    # ------------------------------------------------
    def save_generated_testcase_result(self, file_path: str = GENERATED_TESTCASES_RESULT_PATH):
        if os.path.exists(file_path):
            original_result = load_json(file_path)
            existing_keys = set(
                [get_singe_key_in_dict(item) for item in original_result.get("generated_testcases", [])]
            )

            # 追加不存在的生成记录，避免重复
            for item in original_result.get("generated_testcases", []):
                if get_singe_key_in_dict(item) not in existing_keys:
                    self.generated_testcase_result.setdefault("generated_testcases", []).append(item)

        save_json(file_path=file_path, data=self.generated_testcase_result)
        logger.info(f"Saved generated test case result to {file_path}")

    # ------------------------------------------------
    # 保存测试运行状态（成功 / 失败）
    # ------------------------------------------------
    def save_running_status(self, file_path: str = GENERATED_TESTFILE_RUNNING_STATUS_PATH):
        save_json(
            file_path=file_path,
            data={**self.failed_testfiles_paths, **self.success_testfiles_paths}
        )
        logger.info(f"Saved running status to {file_path}")

    # ------------------------------------------------
    # 保存失败测试类路径列表
    # ------------------------------------------------
    def save_failed_testclass_paths(self, file_path: str = FAILED_TESTFILES_PATH):
        save_json(file_path=file_path, data=self.failed_testfiles_paths)
        logger.info(f"Saved failed test class paths to {file_path}")

    # ------------------------------------------------
    # 保存实验结果（支持增量写入）
    # ------------------------------------------------
    def save_experiment_result(self, incremental_save: bool = False,
                               file_path: str = EXPERIMENT_RESULT_PATH):
        if incremental_save and os.path.exists(file_path):
            self.experiment_result = load_json(file_path)
            self.experiment_result["apt"].update(self.apt_result)
        else:
            self.experiment_result = {
                "original": self.original_result,
                "apt": self.apt_result
            }
        save_json(file_path=file_path, data=self.experiment_result)

    # ------------------------------------------------
    # 执行 APT 测试：Maven 测试 + Jacoco 覆盖率分析
    # ------------------------------------------------
    def run_apt_test(self, testclass_name: str,
                     dest_testcase_path: str) -> bool | List[str]:
        try:
            status = self.run_mvn_test(testclass_name=testclass_name)
            if status is not None:
                return status, "run_mvn_test error"
        except Exception as e:
            logger.error(f"Test failed for class {testclass_name}: {e}")
            return False, "run_mvn_test unknown error"

        try:
            # Jacoco 覆盖率分析
            coverage_result = run_jacoco_coverage_analyzer(
                jar_path=JACOCO_COVERAGE_JAR_PATH,
                exec_file_path=exec_file_path,
                class_files_path=self.class_files_path,
                target_class_name=self.target_class_name,
                target_method_name=self.target_method_name.split("(")[0].split("]")[-1]
            )
            running_status = {
                "name": testclass_name,
                "status": "coverage get success",
                "coverage_result": coverage_result,
            }
            self.incremental_save_running_status(file_name=testclass_name, data=running_status)

            if coverage_result is None:
                raise Exception("No coverage result found")

        except Exception as e:
            logger.error(f"Failed to get coverage for class {testclass_name}: {e}")
            running_status = {
                "name": testclass_name,
                "status": "coverage get error"
            }
            self.incremental_save_running_status(file_name=testclass_name, data=running_status)
            return False, "coverage get error"

        logger.info(f"generated coverage_result: {coverage_result}")

        if coverage_result is None:
            return False, "No coverage result found"

        # 记录方法级覆盖率结果
        self.apt_result[self.key] = coverage_result[self.method_name]
        return True, ""

    # ------------------------------------------------
    # 基于失败日志的测试用例重生成逻辑
    # ------------------------------------------------
    def retry_generate_testcases(self, target_method, parsed_errors,
                                 original_testcase_path, dest_testcase_path):
        regenerated_class_name = self.generator.retry_generate_testcases(
            method=target_method,
            parsed_errors=parsed_errors
        )
        try:
            shutil.copy2(original_testcase_path, dest_testcase_path)
            logger.info(
                f"Successfully copied test case from {original_testcase_path} to {dest_testcase_path}"
            )
            self.success_copied_testcase_paths['success_copied_testcases'].append(dest_testcase_path)
            return regenerated_class_name
        except Exception as e:
            logger.error(f"An error occurred while copying test case: {e}")


# ==================================================
# 以下为模块级辅助函数（不属于 ProjectRunner）
# ==================================================

# --------------------------------------------------
# 创建新的 round 目录，用于增量实验结果
# --------------------------------------------------
def create_round_directory(base_path=RESOLVED_METAINFO_PATH, prefix='round_'):
    round_number = 1
    while True:
        directory_path = os.path.join(base_path, f'{prefix}{round_number}')
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)
            logger.info(f"Create directory: {directory_path}")
            return directory_path, round_number
        round_number += 1


# --------------------------------------------------
# 测试运行入口函数
# --------------------------------------------------
def run_testrunner(generator: TestcaseGenerator):
    method_metainfo = load_json(METHOD_METAINFO_PATH)
    generator = generator()
    runner = ProjectRunner(generator)
    batch_run(method_metainfo=method_metainfo, runner=runner)


# --------------------------------------------------
# 批量运行：多轮生成 → 分析 → 再生成
# --------------------------------------------------
def batch_run(method_metainfo, runner: TestRunner):

    while True:
        success_testcase_paths = run(method_metainfo=method_metainfo, runner=runner)
        logger.info(f"one batch finished, success_testcase_paths: {success_testcase_paths}")

        if not success_testcase_paths:
            logger.info("No more test cases to run, break")
            break

        # 基于最新生成的测试重新构建元信息
        logger.info("Run source parse finished.")
        run_build_metainfo(builder=JavaMetaInfoBuilder())

        # 创建新一轮 round 目录
        directory_path, round_number = create_round_directory()

        # LLM 驱动的测试类分析
        analyzer = JavaTestcaseAnalyzer(llm=DeepSeekLLM())
        incremental_path = os.path.join(directory_path, "testclass_analysis_result.json")

        testclass_analysis_result_paths = [res['file_path'] for res in load_json(TESTCLASS_ANALYSIS_RESULT_PATH)]
        analyzer.batch_incremental_high_level_analyze(testclass_analysis_result_paths=testclass_analysis_result_paths,
                                                    save_path=incremental_path,
                                                    round_number=round_number)
        analyzer.merge_testclass_analysis_result(original_path=TESTCLASS_ANALYSIS_RESULT_PATH,
                                                 incremental_path=incremental_path,
                                                #  save_path=incremental_path.split('.json')[0] + str(round_number) + ".json",
                                                 save_path=TESTCLASS_ANALYSIS_RESULT_PATH)

        # 构建方法 / 类到测试用例的映射关系
        coordinator = JavaNodeCoordinator()
        coordinator.map_method_to_testcase(coordinator.testclass_analysis_result)
        coordinator.map_class_to_testcase()

        logger.info("Run node coordinator finished, start to generate testcase in new round.")

        get_testclass_names()


# --------------------------------------------------
# 判断方法是否为 getter / setter
# --------------------------------------------------
def is_getter_or_setter(method_name):
    return method_name.startswith("get") or method_name.startswith("set")


# --------------------------------------------------
# 单独执行所有方法的覆盖率统计
# --------------------------------------------------
def get_all_methods_coverage():
    llm = DeepSeekLLM()
    runner = ProjectRunner(llm)
    runner.get_all_methods_coverage()


# --------------------------------------------------
# 主执行函数：遍历方法并尝试生成测试用例
# --------------------------------------------------
def run(method_metainfo, runner: TestRunner) -> List[str]:
    success_testcase_paths = []
    target_class = load_class_already_haved_testcase()
    for method in method_metainfo:
        file_path = method["file"]
        # 跳过测试代码中的方法
        if 'test' in file_path:
            logger.info(f"Skipping method {method['name']}, since it may be a test class")
            continue

        # 无返回值的方法（可能是构造器）跳过
        if not method["return_type"]:
            logger.info(f"Skipping method {method['name']}, since it has no return type, may be a constructor")
            continue

        # 私有方法跳过
        modifiers = method['attributes'].get('modifiers', "")
        if modifiers == "private":
            logger.info(f"Skipping method {method['name']}, since it is private")
            continue

        # main 方法跳过
        if 'main' in method['name']:
            logger.info(f"Skipping method {method['name']}, since it is a main method")
            continue

        # 过短的方法跳过（信息量不足）
        num_of_newline = method["original_string"].count('\n')
        if num_of_newline < 3:
            logger.info(f"Skipping method {method['name']}, since it has only 2 line")
            continue

        file_path = method['file']
        class_uri = method["class_uri"]
        target_method_name = '[' + method['uris'][method['uris'].find('[')+1:]
        class_name = class_uri.split('.java.')[-1]
        pure_method_name = target_method_name.split(']')[-1].split('(')[0]
        dest_testcase_path = None

        # 仅对指定类 / 方法运行
        if (
            USE_SPECIFY_CLASS_AND_METHOD and
            class_name not in target_class
        ):
            logger.info(f"Skipping method {method['name']}, since it is not in the specified class or method")
            continue

        # 按路径白名单过滤
        if USE_METHOD_TO_TEST_PATHS:
            for p in METHOD_TO_TEST_PATHS:
                if file_path.startswith(p):
                    dest_testcase_path = runner.run(
                        target_class_uris=class_uri,
                        target_method_name=target_method_name
                    )
                    if dest_testcase_path is not None:
                        success_testcase_paths.append(dest_testcase_path)
                logger.info(
                    f"skipping method {method['name']}, since it is not in the specified path"
                )
        else:
            dest_testcase_path = runner.run(
                target_class_uris=class_uri,
                target_method_name=target_method_name
            )
            if dest_testcase_path is not None:
                success_testcase_paths.append(dest_testcase_path)

    return success_testcase_paths
