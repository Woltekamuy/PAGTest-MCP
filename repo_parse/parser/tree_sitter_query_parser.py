"""
代码解析器：用于从Java源代码中提取特定标识符的方法调用和字段访问信息
基于Tree-sitter语法树解析技术，支持精确的AST节点匹配
"""
import warnings
from tree_sitter_languages import get_language, get_parser  # noqa: E402

warnings.filterwarnings("ignore", category=FutureWarning)

def build_query(query_str, old, new):
    """
     构建动态查询字符串

     参数：
         query_str: 原始查询模板字符串
         old: 需要替换的占位符
         new: 替换后的实际值

     返回：
         替换后的查询字符串

     说明：
         用于将查询模板中的通用占位符替换为具体的标识符名称
     """
    return query_str.replace(old, new)

def extract_identifiers(original_string, invoker_name):
    """
    从Java源代码中提取与指定标识符相关的方法调用和字段访问

    参数：
        original_string: 要解析的Java源代码字符串
        invoker_name: 目标标识符名称（类名或字段名）

    返回：
        tuple[methods_invoked, fields]:
            methods_invoked - 方法调用标识符列表
            fields - 字段访问标识符列表

    异常：
        可能抛出文件读取错误、解析错误等

    工作原理：
        1. 加载预定义的Tree-sitter查询模板
        2. 将模板中的占位符替换为目标标识符
        3. 解析Java源代码生成AST
        4. 执行查询匹配相关节点
        5. 分类提取方法和字段标识符
    """
    language = get_language("java")
    parser = get_parser("java")
    scm_fname = "/home/zhangzhe/APT/repo_parse/parser/queries/java-ref-resolution.scm"
        
    with open (scm_fname, "r") as f:
        query_str = f.read()
        
    query_str = build_query(query_str, r"FieldAccessName", invoker_name)
    query_str = build_query(query_str, r"ClassName", invoker_name)

    tree = parser.parse(bytes(original_string, "utf-8"))
    # Run the tags queries
    query = language.query(query_str)
    captures = query.captures(tree.root_node)
    captures = list(captures)
        
    fields = []
    methods_invoked = []
    for node, tag in captures:        
        if tag.startswith("field.access.identifier"):
            # print(node.text.decode("utf-8"))
            fields.append(node.text.decode("utf-8"))
        if tag.startswith("method.invocation.identifier"):
            # print(node.text.decode("utf-8"))
            methods_invoked.append(node.text.decode("utf-8"))

    return methods_invoked, fields