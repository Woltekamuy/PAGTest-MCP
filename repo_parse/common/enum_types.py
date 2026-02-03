# ============================================================
# 模块说明：
# 本模块用于定义代码分析与处理过程中所支持的编程语言枚举，
# 以及语言与其对应文件后缀之间的映射关系。
# ============================================================
from enum import Enum


class LanguageEnum(Enum):
    PYTHON = "python"   # Python 语言
    JAVA = "java"       # Java 语言
    CPP = "cpp"         # C++ 语言
    GO = "go"           # Go 语言


# ------------------------------------------------------------
# LANGUAGE_TO_SUFFIX
# ------------------------------------------------------------
# 编程语言到源代码文件后缀的映射表
# ------------------------------------------------------------
LANGUAGE_TO_SUFFIX = {
    LanguageEnum.PYTHON: "py",
    LanguageEnum.JAVA: "java",
    LanguageEnum.CPP: "cpp",
    LanguageEnum.GO: "go",
}
