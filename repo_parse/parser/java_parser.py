"""
JavaParser - Java源代码解析器

此模块使用Tree-sitter将Java文件解析为source_parser schema定义的结构化组件
是程序的主要入口点，提供Java语言特定的解析功能
"""

"""
java_parser.py - Java源代码解析器

该类使用Tree-sitter将Java文件解析为由source_parser schema定义的结构化组件

Java解析器针对类输出的特定schema：
[{
    'name': '类名',
    'original_string': '类的完整原始字符串',
    'body': '类主体的原始字符串',
    'class_docstring': '类前的注释（Javadoc）',
    'definition': '定义类的签名、名称和修饰符',
    'syntax_pass': True/False,  # 语法检查是否通过

    'attributes': {
        'comments': ['出现在类修饰符中的注释列表'],
        'marker_annotations': ['@marker1', '@marker2', ...],  # 标记注解
        'modifiers': '修饰符的原始字符串',
        'non_marker_annotations': ['public/private/static等非标记、非注释的修饰符列表'],

        'fields': [{  # 字段定义列表
            'comments': ['出现在字段修饰符中的注释列表'],
            'docstring': '字段前的注释',
            'marker_annotations': ['@marker1', '@marker2', ...],
            'modifiers': '@marker1\n    public',  # 修饰符原始字符串
            'name': 'field_name',
            'non_marker_annotations': ['public', 'static, ...],
            'attribute_expression': '字段的原始字符串',
            'syntax_pass': True/False,
            'type': 'int, 类型',  # 字段类型
        }, ... ],  # 注意：字段没有'attributes'键，这与类和方法不同

        'classes': [...],  # 嵌套类
    },

    'methods': [{  # 方法定义列表
        'attributes': {
            'comments': ['出现在方法修饰符中的注释列表'],
            'marker_annotations': ['@marker1', '@marker2', ...],
            'modifiers': '修饰符原始字符串',
            'non_marker_annotations': ['public/private/static等非标记、非注释的修饰符列表'],
            'return_type': '返回类型',
        },
        'body': '方法体的原始字符串',
        'docstring': '方法前的注释（Javadoc）',
        'name': '方法名',
        'original_string': '整个方法的原始字符串',
        'signature': '方法签名的原始字符串',
        'syntax_pass': True/False,
        'classes': [...],  # 嵌套类（方法内部定义的类）
    }, ...],
}, ... ]

不支持处理：
 - 签名/类定义内部的注释
 - 方法/类体内部的注释（除了Javadoc）
 - 类定义之间的注释（除了Javadoc）
这些通常包含在verbatim/original_string字段中，但如果位于结构之间或非Javadoc，可能会被忽略。
"""

from typing import List

# 导入基础解析器和工具函数
from source_parser.parsers.language_parser import (
    LanguageParser,  # 基础语言解析器抽象类
    has_correct_syntax,  # 语法正确性检查
    children_of_type,  # 获取特定类型的子节点
    children_not_of_type,  # 获取非特定类型的子节点
    previous_sibling,  # 获取前一个兄弟节点
)
from source_parser.parsers.commentutils import strip_c_style_comment_delimiters  # 去除C风格注释分隔符
from source_parser.utils import static_hash  # 静态哈希计算工具


class RefineJavaParser(LanguageParser):
    """
    Java源代码结构特征提取解析器

    将Java源代码提取到source_parser schema中，支持：
    - 类、接口、记录（record）的解析
    - 方法、字段的提取
    - 修饰符、注解的分析
    - 继承关系的处理
    - 语法正确性验证
    """

    # 节点类型定义常量
    _method_types = (
        "constructor_declaration",  # 构造函数声明
        "method_declaration",  # 方法声明
    )
    _class_types = ("class_declaration",)  # 类声明
    _interface_types = ("interface_declaration",)  # 接口声明
    _record_types = ("record_declaration",)  # 记录声明（Java 14+）
    _record_constructor_types = ("compact_constructor_declaration",)  # 记录紧凑构造函数
    _import_types = (
        "import_declaration",  # 导入声明
        "package_declaration",  # 包声明
    )
    _docstring_types = ("comment", "line_comment", "block_comment")  # 文档注释类型
    _include_patterns = "*?.java"  # 文件包含模式，匹配Java文件

    @property
    def schema(self):
        """
        文件级别的schema结构

        返回包含以下键的字典：
        - file_hash: 文件内容的静态哈希值，用于唯一标识
        - file_docstring: 文件顶层的注释（不是类的Javadoc）
        - contexts: 文件上下文（导入和包声明列表）
        - methods: 顶层方法列表，通过parse_method_node解析
        - classes: 顶层类列表，通过parse_class_node解析
        - interfaces: 顶层接口列表，通过parse_interface_node解析
        - records: 顶层记录列表，通过parse_record_node解析

        详细schema描述请参见顶层README.md文件
        """
        return {
            "file_hash": static_hash(self.file_bytes),  # 计算文件哈希
            "file_docstring": self.file_docstring,  # 提取文件文档字符串
            "contexts": self.file_context,  # 获取文件上下文信息
            "methods": [self.parse_method_node(c) for c in self.method_nodes],  # 解析所有方法
            "classes": [self.parse_class_node(c) for c in self.class_nodes],  # 解析所有类
            "interfaces": [self.parse_interface_node(c) for c in self.interface_nodes],  # 解析所有接口
            "records": [self.parse_record_node(c) for c in self.record_nodes],  # 解析所有记录
        }

    @classmethod
    def get_lang(cls):
        """返回语言标识符"""
        return "java"

    @property
    def method_types(self):
        """返回方法节点类型元组"""
        return self._method_types

    @property
    def record_constructor_types(self):
        """返回记录构造函数节点类型"""
        return self._record_constructor_types

    @property
    def class_types(self):
        """返回类节点类型字符串"""
        return self._class_types

    @property
    def interface_types(self):
        """返回接口节点类型字符串"""
        return self._interface_types

    @property
    def interface_nodes(self):
        """
        顶层接口节点列表

        这些节点将传递给self.parse_interface_node进行解析
        返回根节点中类型为接口声明的所有子节点
        """
        return children_of_type(self.tree.root_node, self.interface_types)

    @property
    def record_types(self):
        """返回记录节点类型字符串"""
        return self._record_types

    @property
    def record_nodes(self):
        """
        顶层记录节点列表

        这些节点将传递给self.parse_record_node进行解析
        返回根节点中类型为记录声明的所有子节点
        """
        return children_of_type(self.tree.root_node, self.record_types)

    @property
    def import_types(self):
        """返回导入节点类型字符串"""
        return self._import_types

    @property
    def include_patterns(self):
        """返回文件包含模式"""
        return self._include_patterns

    @property
    def __file_docstring_nodes(self):
        """返回顶层注释节点列表"""
        return children_of_type(self.tree.root_node, self._docstring_types)

    def _get_docstring_before(self, node, parent_node=None):
        """
        返回节点前的文档字符串节点

        参数：
            node: 目标节点
            parent_node: 父节点，默认为None时使用根节点

        返回：
            如果前一个兄弟节点是文档注释，返回该节点；否则返回None
        """
        if parent_node is None:
            parent_node = self.tree.root_node

        prev_sib = previous_sibling(node, parent_node)
        if prev_sib is None:
            return None
        if prev_sib.type in self._docstring_types:
            return prev_sib
        return None

    @property
    def file_docstring(self):
        """
        文件文档字符串

        返回文件中第一个不是类的Javadoc的顶层单行或多行注释。
        如果第一个非Javadoc注释在Javadoc注释之后（即在类之间），则忽略它。
        （仅考虑文件开头的注释）
        """
        # 获取所有类前的注释节点
        class_comment_nodes = [
            self._get_docstring_before(c_node) for c_node in self.class_nodes
        ]

        # 检查第一个文档注释节点是否不是类注释
        if len(self.__file_docstring_nodes) > 0:
            if self.__file_docstring_nodes[0] not in class_comment_nodes:
                return strip_c_style_comment_delimiters(
                    self.span_select(self.__file_docstring_nodes[0])
                )
        return ""

    @property
    def file_context(self) -> List[str]:
        """
        文件上下文信息

        返回全局导入和赋值语句的列表。
        注意：Java中没有全局赋值语句，只有导入和包声明。
        """
        # 获取所有导入和包声明节点
        file_context_nodes = children_of_type(self.tree.root_node, self._import_types)
        return [self.span_select(node) for node in file_context_nodes]

    def _parse_super_interfaces_list(self, extends_interfaces_node, parent_node=None):
        """
        解析接口继承列表

        参数：
            extends_interfaces_node: 扩展接口节点
            parent_node: 父节点（可选）

        返回：
            继承的接口名称列表
        """
        result = []
        for child in extends_interfaces_node[0].children:
            if child.type == "type_list":  # 类型列表节点
                for node in child.children:
                    if node.type == "type_identifier":  # 类型标识符
                        result.append(self.span_select(node, indent=False))
                    elif node.type == "generic_type":  # 泛型类型
                        result.append(self.span_select(node, indent=False))
        return result

    def parse_interface_node(self, interface_node, parent_node=None):
        """
        解析接口节点

        参数：
            interface_node: 接口声明节点
            parent_node: 父节点（可选）

        返回：
            包含接口信息的字典，格式符合schema定义
        """
        class_dict = {}
        attributes = {}

        # 基础接口信息
        class_dict = {
            "original_string": self.span_select(interface_node),  # 原始字符串
            "definition": self.span_select(*interface_node.children[:-1]),  # 定义部分
        }

        # 查找接口前的Javadoc注释
        docstring_node = self._get_docstring_before(interface_node, parent_node)
        class_dict["interface_docstring"] = (
            strip_c_style_comment_delimiters(self.span_select(docstring_node))
            if docstring_node
            else ""
        )

        # 解析修饰符
        modifiers_node_list = children_of_type(interface_node, "modifiers")
        modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
        attributes.update(modifiers_attributes)

        # 解析接口名称
        name_node = children_of_type(interface_node, "identifier")[0]
        class_dict["name"] = (
            self.span_select(name_node, indent=False) if name_node else ""
        )

        # 解析接口继承：public interface MyInterface extends SomeOtherInterface, Hereo
        extends_interfaces_node = children_of_type(interface_node, "extends_interfaces")
        if len(extends_interfaces_node) == 0:
            extends_interfaces = []
        else:
            extends_interfaces = self._parse_super_interfaces_list(extends_interfaces_node)
        class_dict['extends_interfaces'] = extends_interfaces

        # 获取接口体
        body_node = interface_node.child_by_field_name("body")

        class_dict["attributes"] = attributes  # 设置属性字典
        class_dict["syntax_pass"] = has_correct_syntax(interface_node)  # 语法检查

        # 解析接口中的方法
        class_dict["methods"] = [
            self._parse_method_node(m, body_node)
            for m in children_of_type(body_node, self.method_types)
        ]

        return class_dict

    def parse_record_node(self, record_node, parent_node=None):
        """
        解析记录（record）节点（Java 14+特性）

        参数：
            record_node: 记录声明节点
            parent_node: 父节点（可选）

        返回：
            包含记录信息的字典，格式符合schema定义
        """
        attributes = {}

        # 基础记录信息
        record_dict = {
            "original_string": self.span_select(record_node),  # 原始字符串
            "name": "",  # 记录名称
            "fields": [],  # 记录字段列表
            "constructors": "",  # 构造函数
            "methods": [],  # 方法列表
        }

        # 查找记录前的Javadoc注释
        docstring_node = self._get_docstring_before(record_node, parent_node)
        record_dict["class_docstring"] = (
            strip_c_style_comment_delimiters(self.span_select(docstring_node))
            if docstring_node
            else ""
        )

        # 解析修饰符
        modifiers_node_list = children_of_type(record_node, "modifiers")
        modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
        attributes.update(modifiers_attributes)

        # 解析记录名称
        name_node = children_of_type(record_node, "identifier")[0]
        record_dict["name"] = (
            self.span_select(name_node, indent=False) if name_node else ""
        )

        # 解析记录参数（记录字段）
        parameters_node_list = children_of_type(record_node, "formal_parameters")[0]
        record_dict["fields"] = [
            self._parse_param_node(p) for p in parameters_node_list.children if p.type == "formal_parameter"
        ]

        # 获取记录体
        body_node = record_node.child_by_field_name("body")

        record_dict["attributes"] = attributes  # 设置属性字典
        record_dict["syntax_pass"] = has_correct_syntax(record_node)  # 语法检查

        # 解析紧凑构造函数
        record_dict['constructors'] = [
            self._parse_record_constructor_node(m, body_node)
            for m in children_of_type(body_node, self.record_constructor_types)
        ]

        # 解析记录中的方法
        record_dict["methods"] = [
            self._parse_method_node(m, body_node)
            for m in children_of_type(body_node, self.method_types)
        ]

        return record_dict

    def _parse_record_constructor_node(self, method_node, parent_node=None):
        """
        解析记录紧凑构造函数节点

        参数：
            method_node: 构造函数节点
            parent_node: 父节点（可选）

        返回：
            包含构造函数信息的字典
        """
        # 确保节点类型正确
        assert method_node.type in self.record_constructor_types

        # 基础构造函数信息
        method_dict = {
            "syntax_pass": has_correct_syntax(method_node),  # 语法检查
            "original_string": self.span_select(method_node),  # 原始字符串
        }

        # 查找构造函数前的注释
        comment_node = self._get_docstring_before(method_node, parent_node)
        method_dict["docstring"] = (
            strip_c_style_comment_delimiters(
                self.span_select(comment_node, indent=False)
            )
            if comment_node
            else ""
        )

        # 解析修饰符
        modifiers_node_list = children_of_type(method_node, "modifiers")
        modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
        method_dict["attributes"] = modifiers_attributes

        return method_dict

    def _parse_param_node(self, param_node, parent_node=None):
        """
        解析参数节点

        参数：
            param_node: 参数节点
            parent_node: 父节点（可选）

        返回：
            包含参数名称和类型的字典
        """
        return {
            "name": self.span_select(param_node.child_by_field_name("name"), indent=False),  # 参数名
            "type": self.span_select(param_node.child_by_field_name("type"), indent=False),  # 参数类型
        }

    def _parse_method_node(self, method_node, parent_node=None):
        """
        解析方法节点

        参数：
            method_node: 方法声明节点
            parent_node: 父节点（可选）

        返回：
            包含方法信息的字典，格式符合schema定义

        详细文档请参见LanguageParser.parse_method_node
        """
        # 确保节点类型正确
        assert method_node.type in self.method_types

        # 基础方法信息
        method_dict = {
            "syntax_pass": has_correct_syntax(method_node),  # 语法检查
            "original_string": self.span_select(method_node),  # 原始字符串
        }

        # 查找方法前的Javadoc注释
        comment_node = self._get_docstring_before(method_node, parent_node)
        method_dict["docstring"] = (
            strip_c_style_comment_delimiters(
                self.span_select(comment_node, indent=False)
            )
            if comment_node
            else ""
        )

        # 解析修饰符
        modifiers_node_list = children_of_type(method_node, "modifiers")
        modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
        method_dict["attributes"] = modifiers_attributes

        # 解析返回类型
        type_node = method_node.child_by_field_name("type")
        method_dict["attributes"]["return_type"] = (
            self.span_select(type_node, indent=False) if type_node else ""
        )

        # 解析方法名称
        name_node = children_of_type(method_node, "identifier")[0]
        method_dict["name"] = (
            self.span_select(name_node, indent=False) if name_node else ""
        )

        # 解析参数列表
        parameters_node_list = children_of_type(method_node, "formal_parameters")[0]
        method_dict["params"] = [
            self._parse_param_node(p) for p in parameters_node_list.children if p.type == "formal_parameter"
        ]

        # 解析方法体
        body_node = method_node.child_by_field_name("body")
        method_dict["body"] = (
            self.span_select(body_node) if body_node else ""
        )

        # 解析方法签名（包含参数）
        method_dict["signature"] = self.span_select(
            method_node, children_of_type(method_node, "formal_parameters")[0],
            indent=False
        )

        # 获取嵌套类（方法内部定义的类）
        classes = (
            [
                self._parse_class_node(c, body_node)
                for c in children_of_type(body_node, "class_declaration")
            ]
            if body_node
            else []
        )
        method_dict["attributes"]["classes"] = classes

        return method_dict

    def _parse_modifiers_node_list(self, modifiers_node_list):
        """
        解析修饰符节点列表

        参数：
            modifiers_node_list: 修饰符节点列表

        返回：
            包含修饰符信息的字典：
            - modifiers: 修饰符原始字符串
            - marker_annotations: 标记注解列表
            - non_marker_annotations: 非标记注解列表
            - comments: 注释列表
        """
        attributes = {}
        if len(modifiers_node_list) > 0:  # 通常不会超过1个
            modifiers_node = modifiers_node_list[0]
            attributes["modifiers"] = self.span_select(modifiers_node, indent=False)  # 原始修饰符字符串

            # 提取标记注解（如@Deprecated）
            attributes["marker_annotations"] = [
                self.span_select(m, indent=False)
                for m in children_of_type(modifiers_node, "marker_annotation")
            ]

            # 提取非标记注解（如public、private、static等）
            attributes["non_marker_annotations"] = self.select(
                children_not_of_type(
                    modifiers_node, ["marker_annotation", ] + list(self._docstring_types)
                ),
                indent=False,
            )

            # 提取注释
            attributes["comments"] = self.select(
                children_of_type(modifiers_node, self._docstring_types), indent=False
            )
        else:
            # 无修饰符时的默认值
            attributes["modifiers"] = ""
            attributes["marker_annotations"] = []
            attributes["non_marker_annotations"] = []
            attributes["comments"] = []
        return attributes

    def _parse_superclass_node(self, superclass_node):
        """
        解析父类节点

        参数：
            superclass_node: 父类声明节点

        返回：
            父类名称字符串
        """
        superclass = children_of_type(superclass_node, "type_identifier")
        return self.span_select(superclass[0], indent=False) if superclass else ""

    def _parse_class_node(self, class_node, parent_node=None):
        """
        解析类节点

        参数：
            class_node: 类声明节点
            parent_node: 父节点（可选）

        返回：
            包含类信息的字典，格式符合schema定义
        """
        class_dict = {}
        attributes = {}

        # 基础类信息
        class_dict = {
            "original_string": self.span_select(class_node),  # 原始字符串
            "definition": self.span_select(*class_node.children[:-1]),  # 定义部分
        }

        # 查找类前的Javadoc注释
        docstring_node = self._get_docstring_before(class_node, parent_node)
        class_dict["class_docstring"] = (
            strip_c_style_comment_delimiters(self.span_select(docstring_node))
            if docstring_node
            else ""
        )

        # 解析修饰符
        modifiers_node_list = children_of_type(class_node, "modifiers")
        modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
        attributes.update(modifiers_attributes)

        # 解析类名称
        name_node = children_of_type(class_node, "identifier")[0]
        class_dict["name"] = (
            self.span_select(name_node, indent=False) if name_node else ""
        )

        # 解析接口实现：class UserRestClient implements DDD, EEEE
        super_interfaces_node_list = children_of_type(class_node, "super_interfaces")
        if len(super_interfaces_node_list) == 0:
            class_dict["super_interfaces"] = []
        else:
            super_interfaces = self._parse_super_interfaces_list(super_interfaces_node_list)
            class_dict["super_interfaces"] = super_interfaces

        # 解析父类继承：class UserRestClient extends AAA
        superclass_node_list = children_of_type(class_node, "superclass")
        if len(superclass_node_list) == 0:
            class_dict["superclasses"] = ""
        else:
            class_dict["superclasses"] = self._parse_superclass_node(superclass_node_list[0])

        # 获取类体
        body_node = class_node.child_by_field_name("body")

        # 解析字段
        fields = []
        for f in children_of_type(body_node, "field_declaration"):
            field_dict = {}

            field_dict["attribute_expression"] = self.span_select(f, indent=False)  # 字段原始表达式

            # 查找字段前的注释
            comment_node = self._get_docstring_before(f, body_node)
            field_dict["docstring"] = (
                strip_c_style_comment_delimiters(
                    self.span_select(comment_node, indent=False)
                )
                if comment_node
                else ""
            )

            # 解析字段修饰符
            modifiers_node_list = children_of_type(f, "modifiers")
            modifiers_attributes = self._parse_modifiers_node_list(modifiers_node_list)
            field_dict.update(modifiers_attributes)

            # 解析字段类型
            type_node = f.child_by_field_name("type")
            field_dict["type"] = self.span_select(type_node, indent=False)

            # 解析字段名称
            declarator_node = f.child_by_field_name("declarator")
            field_dict["name"] = (
                self.span_select(declarator_node, indent=False)
                if declarator_node
                else ""
            )

            field_dict["syntax_pass"] = has_correct_syntax(f)  # 语法检查

            fields.append(field_dict)
        attributes["fields"] = fields  # 设置字段列表

        # 获取嵌套类
        classes = (
            [
                self._parse_class_node(c, body_node)
                for c in children_of_type(body_node, "class_declaration")
            ]
            if body_node
            else []
        )
        attributes["classes"] = classes  # 设置嵌套类列表

        class_dict["attributes"] = attributes  # 设置属性字典
        class_dict["syntax_pass"] = has_correct_syntax(class_node)  # 语法检查
        # 解析类中的方法
        class_dict["methods"] = [
            self._parse_method_node(m, body_node)
            for m in children_of_type(body_node, self.method_types)
        ]

        return class_dict