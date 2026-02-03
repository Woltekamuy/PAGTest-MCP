"""
代码元数据模型定义模块

本模块定义了用于表示源代码结构化信息的核心数据模型，
包括类、方法、文件等实体及其属性，支持Java语言的特殊特性。
这些模型用于在解析器输出和后续分析之间提供标准化的数据结构。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List


class Method:
    """
    方法元数据类

    表示源代码中的一个方法，包含方法的所有相关信息，
    如名称、参数、返回类型、签名、文档字符串等。

    属性：
        uris (List[str] | str): 方法的唯一标识符URI列表或字符串
        name (str): 方法名称
        arg_nums (str): 参数数量
        params (str): 参数字符串表示
        signature (str): 方法签名（包含参数类型）
        original_string (str): 方法的原始源代码字符串
        default_arguments (Dict[str, str]): 默认参数值字典，键为参数名，值为默认值
        file (str): 方法所在的文件路径
        class_name (str): 所属类名
        class_uri (str): 所属类的URI标识
        attributes (Dict[str, List[str]]): 方法属性字典，如修饰符、注解等
        docstring (str): 方法文档字符串（Javadoc）
        return_type (str): 返回类型
    """

    def __init__(self,
                 uris: List[str] | str = None,
                 name: str = None,
                 arg_nums: str = None,
                 params: str = None,
                 signature: str = None,
                 original_string: str = None,
                 default_arguments: Dict[str, str] = None,
                 file: str = None,
                 class_name: str = None,
                 class_uri: str = None,
                 attributes: Dict[str, List[str]] = None,
                 docstring: str = None,
                 return_type: str = None):
        # 方法标识信息
        self.uris = uris
        self.name = name
        self.arg_nums = arg_nums
        self.params = params

        # 方法定义信息
        self.signature = signature
        self.original_string = original_string
        self.default_arguments = default_arguments

        # 上下文信息
        self.file = file
        self.class_name = class_name
        self.class_uri = class_uri

        # 元数据和文档
        self.attributes = attributes
        self.docstring = docstring
        self.return_type = return_type

    def to_json(self) -> Dict:
        """
        将方法对象转换为JSON可序列化字典

        返回：
            Dict: 包含所有方法属性的字典
        """
        return {
            "uris": self.uris,
            "name": self.name,
            "arg_nums": self.arg_nums,
            "params": self.params,
            "return_type": self.return_type,
            "signature": self.signature,
            "original_string": self.original_string,
            "default_arguments": self.default_arguments,
            "file": self.file,
            "class_name": self.class_name,
            "class_uri": self.class_uri,
            "attributes": self.attributes,
            "docstring": self.docstring,
        }


class Class:
    """
    类元数据基类

    表示源代码中的一个类，包含类的基本信息。
    这是所有具体类类型（普通类、抽象类、接口等）的基类。

    属性：
        uris (List[str]): 类的唯一标识符URI列表
        name (str): 类名
        file_path (str): 类所在的文件路径
        superclasses (List[str]): 父类列表
        methods (List[str]): 类中定义的方法名列表
        method_uris (List[List[str]]): 方法URI列表的列表，与methods对应
        overrides (List[str]): 重写的父类方法名列表
        attributes (Dict[str, List[str]]): 类属性字典，如修饰符、注解等
        class_docstring (str): 类文档字符串（Javadoc）
        original_string (str): 类的原始源代码字符串
    """

    def __init__(self,
                 uris: List[str] = None,
                 name: str = None,
                 file_path: str = None,
                 superclasses: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 ):
        # 类标识信息
        self.uris = uris
        self.name = name
        self.file_path = file_path

        # 继承关系
        self.superclasses = superclasses
        self.overrides = overrides  # 重写的方法列表

        # 类成员
        self.methods = methods
        self.method_uris = method_uris

        # 元数据和文档
        self.attributes = attributes
        self.class_docstring = class_docstring
        self.original_string = original_string

    def to_json(self) -> Dict:
        """
        将类对象转换为JSON可序列化字典

        返回：
            Dict: 包含所有类属性的字典
        """
        return {
            "uris": self.uris,
            "name": self.name,
            "file_path": self.file_path,
            "superclasses": self.superclasses,
            "methods": self.methods,
            "method_uris": self.method_uris,
            "overrides": self.overrides,
            "attributes": self.attributes,
            "class_docstring": self.class_docstring,
            "original_string": self.original_string
        }


class JavaClass(Class):
    """
    Java类元数据类

    扩展自Class类，添加Java特有的属性，如接口实现和字段信息。

    额外属性：
        super_interfaces (List[str]): 实现的接口列表
        fields (List[Dict]): 字段定义列表，每个字段为字典形式
    """

    def __init__(self,
                 uris: List[str] | str = None,
                 name: str = None,
                 file_path: str = None,
                 superclasses: List[str] = None,
                 super_interfaces: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 fields: List[Dict] = None,
                 ):
        # 调用父类构造函数初始化基本属性
        super().__init__(uris, name, file_path, superclasses, methods,
                         method_uris, overrides, attributes,
                         class_docstring, original_string)

        # Java特有属性
        self.super_interfaces = super_interfaces  # 实现的接口
        self.fields = fields  # 字段定义列表

    def to_json(self) -> Dict:
        """
        将Java类对象转换为JSON可序列化字典，包含父类属性和Java特有属性

        返回：
            Dict: 包含所有属性的字典
        """
        # 合并父类和子类的属性
        return {
            **super().to_json(),  # 包含父类所有属性
            "super_interfaces": self.super_interfaces,
            "fields": self.fields,
        }


class JavaAbstractClass(JavaClass):
    """
    Java抽象类元数据类

    表示Java中的抽象类，继承自JavaClass，目前没有额外属性，
    主要用于类型区分和未来可能的扩展。
    """

    def __init__(self,
                 uris: List[str] | str = None,
                 name: str = None,
                 file_path: str = None,
                 superclasses: List[str] = None,
                 super_interfaces: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 fields: List[Dict] = None,
                 ):
        # 直接调用JavaClass的构造函数，抽象类没有额外特殊属性
        super().__init__(uris, name, file_path, superclasses, super_interfaces,
                         methods, method_uris, overrides, attributes,
                         class_docstring, original_string, fields)


class JavaRecord(JavaClass):
    """
    Java记录（Record）元数据类

    表示Java 14+引入的记录类型，是一种特殊形式的类，
    主要用于不可变数据的载体。

    注意：记录通常不包含字段列表以外的额外状态，构造函数自动生成。
    """

    def __init__(self,
                 uris: List[str] | str = None,
                 name: str = None,
                 superclasses: List[str] = None,
                 super_interfaces: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 fields: List[Dict] = None,
                 ):
        # 调用父类构造函数，但忽略某些不适合记录的属性
        super().__init__(uris, name, None, superclasses, methods,
                         method_uris, overrides, attributes,
                         class_docstring, original_string)
        self.fields = fields  # 记录的核心是字段定义

    def to_json(self) -> Dict:
        """
        将Java记录对象转换为JSON可序列化字典

        返回：
            Dict: 包含记录属性的字典
        """
        return {
            "uris": self.uris,
            "name": self.name,
            "methods": self.methods,
            "attributes": self.attributes,
            "class_docstring": self.class_docstring,
            "original_string": self.original_string,
            "fields": self.fields
        }


class JavaInterface(JavaClass):
    """
    Java接口元数据类

    表示Java中的接口类型，继承自JavaClass，
    但接口不能有字段和具体实现，只能有方法声明。
    """

    def __init__(self,
                 uris: List[str] | str = None,
                 name: str = None,
                 file_path: str = None,
                 superclasses: List[str] = None,
                 super_interfaces: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 fields: List[Dict] = None,
                 ):
        # 接口没有字段，也不应继承super_interfaces参数
        super().__init__(
            uris=uris,
            name=name,
            file_path=file_path,
            superclasses=superclasses,
            super_interfaces=None,  # 接口的父接口在superclasses中表示
            methods=methods,
            method_uris=method_uris,
            overrides=overrides,
            attributes=attributes,
            class_docstring=class_docstring,
            original_string=original_string,
            fields=None)  # 接口不能有字段

    def to_json(self) -> Dict:
        """
        将Java接口对象转换为JSON可序列化字典

        返回：
            Dict: 包含接口属性的字典
        """
        return {
            "uris": self.uris,
            "name": self.name,
            "file_path": self.file_path,
            "superclasses": self.superclasses,
            "methods": self.methods,
            "method_uris": self.method_uris,
            "overrides": self.overrides,
            "attributes": self.attributes,
            "class_docstring": self.class_docstring,
            "original_string": self.original_string
        }


class FileType(Enum):
    """
    文件类型枚举

    用于标识源代码文件的类型，支持不同类型文件的差异化处理。

    枚举值：
        NORMAL: 普通源代码文件
        TEST: 测试文件
        CONFIG: 配置文件
    """
    NORMAL = 1
    TEST = 2
    CONFIG = 3


class File:
    """
    文件元数据类

    表示一个源代码文件，包含文件中的所有结构化信息。

    属性：
        name (str): 文件名
        file_path (str): 文件完整路径
        original_string (str): 文件原始内容
        context (List[str]): 文件上下文，如导入语句、包声明等
        global_variables (List[Dict[str, str]]): 全局变量列表（Java中通常为空）
        methods (List[Dict[Any, Any]]): 文件中定义的方法列表
        classes (List[Dict[Any, Any]]): 文件中定义的类列表
        file_type (FileType): 文件类型枚举值
    """

    def __init__(self,
                 name: str = None,
                 file_path: str = None,
                 original_string: str = None,
                 context: List[str] = None,
                 global_variables: List[Dict[str, str]] = None,
                 methods: List[Dict[Any, Any]] = None,
                 classes: List[Dict[Any, Any]] = None,
                 file_type: FileType = None
                 ) -> None:
        # 文件基本信息
        self.name = name
        self.file_path = file_path
        self.original_string = original_string

        # 文件内容结构
        self.context = context
        self.global_variables = global_variables
        self.methods = methods
        self.classes = classes

        # 文件分类
        self.file_type = file_type

    def to_json(self) -> Dict:
        """
        将文件对象转换为JSON可序列化字典

        返回：
            Dict: 包含所有文件属性的字典
        """
        # 将枚举类型转换为字符串表示
        file_type_str = self.file_type.name if self.file_type else None

        return {
            'name': self.name,
            'file_path': self.file_path,
            'original_string': self.original_string,
            'context': self.context,
            'global_variables': self.global_variables,
            'methods': self.methods,
            'classes': self.classes,
            'file_type': file_type_str
        }


class MethodSignature(ABC):
    """
    方法签名抽象基类

    定义方法签名的通用接口，用于生成方法的唯一标识符。
    不同语言可以有不同的实现方式。

    属性：
        file_path (str): 方法所在文件路径
        class_name (str): 方法所属类名
        method_name (str): 方法名
    """

    def __init__(self, file_path: str = None,
                 class_name: str = None,
                 method_name: str = None) -> None:
        self.file_path = file_path
        self.class_name = class_name
        self.method_name = method_name

    @abstractmethod
    def unique_name(self) -> str:
        """
        生成方法的唯一标识符

        返回：
            str: 方法的唯一名称，通常包含文件、类、方法名和参数类型信息

        注意：
            这是抽象方法，子类必须实现
        """
        pass


class JavaMethodSignature(MethodSignature):
    """
    Java方法签名实现类

    生成Java方法的唯一标识符，考虑参数类型和返回类型。

    额外属性：
        params (List[Dict[str, str]]): 参数列表，每个参数包含名称和类型
        return_type (str): 返回类型
    """

    def __init__(self,
                 file_path: str = None,
                 class_name: str = None,
                 method_name: str = None,
                 params: List[Dict[str, str]] = None,
                 return_type: str = None) -> None:
        # 调用父类构造函数
        MethodSignature.__init__(self, file_path, class_name, method_name)

        # Java特有属性
        self.params = params
        self.return_type = return_type

    def unique_name(self) -> str:
        """
        生成Java方法的唯一标识符

        格式：文件路径.类名.[返回类型]方法名(参数类型1,参数类型2,...)

        示例："/src/Test.java.User.[String]getName()"

        返回：
            str: 方法的唯一标识符
        """
        # 构建参数类型字符串
        param_types = ','.join([param['type'] for param in self.params]) if self.params else ''

        # 组装唯一标识符
        return (f"{self.file_path}.{self.class_name}."
                f"[{self.return_type}]{self.method_name}"
                f"({param_types})")


class TestCase:
    """
    测试用例标记接口

    这是一个空类，用于类型标记，表示该类或方法是测试相关的。
    通过多重继承来标记测试类或测试方法。
    """
    pass
class TestMethod(Method, TestCase):
    """
    测试方法元数据类

    表示一个测试方法，继承自Method和TestCase。
    目前没有额外属性，主要用于类型区分。
    """

    def __init__(self,
                 uris: List[str] = None,
                 name: str = None,
                 arg_nums: str = None,
                 params: str = None,
                 signature: str = None,
                 original_string: str = None,
                 default_arguments: Dict[str, str] = None,
                 file: str = None,
                 class_name: str = None,class_uri: str = None,
                 attributes: Dict[str, List[str]] = None,
                 docstring: str = None,
                 return_type: str = None
                 ):
        # 调用父类Method的构造函数
        super().__init__(
            uris, name, arg_nums, params, signature, original_string,default_arguments, file, class_name, class_uri,attributes, docstring, return_type)
    def to_json(self) -> Dict:
        """
        将测试方法对象转换为JSON可序列化字典

        返回：
            Dict: 继承自Method的JSON表示
        """
        return super().to_json()


class TestClass(Class, TestCase):
    """
    测试类元数据类

    表示一个测试类，继承自Class和TestCase。
    目前没有额外属性，主要用于类型区分。
    """

    def __init__(self,
                 uris: List[str] = None,
                 name: str = None,
                 superclasses: List[str] = None,
                 methods: List[str] = None,
                 method_uris: List[List[str]] = None,
                 overrides: List[str] = None,  # 重写的父类方法
                 attributes: Dict[str, List[str]] = None,
                 class_docstring: str = None,
                 original_string: str = None,
                 ):
        # 调用父类Class的构造函数
        super().__init__(uris, name, None, superclasses, methods,
                         method_uris, overrides, attributes,
                         class_docstring, original_string)

    def to_json(self) -> Dict:
        """
        将测试类对象转换为JSON可序列化字典

        返回：
            Dict: 继承自Class的JSON表示
        """
        return super().to_json()
