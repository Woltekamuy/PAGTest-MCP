# ============================================================
# ScopeGraph 模块
# ------------------------------------------------------------
# 本模块基于有向图（networkx.DiGraph）构建“作用域图（Scope Graph）”，
# 用于表示源代码中：
#   - 作用域（Scope）
#   - 定义（Definition）
#   - 引用（Reference）
#   - 导入（Import）
# 以及它们之间的关系（边类型由 EdgeKind 描述）。
# ============================================================

from networkx import DiGraph, dfs_postorder_nodes
from typing import Dict, Optional, Iterator, List

from repo_parse.scope_graph.utils import TextRange
from .imports import LocalImportStmt
from .definition import LocalDef
from .reference import Reference
from .scope import LocalScope, ScopeStack
from .graph_types import NodeKind, EdgeKind, ScopeNode, ScopeID


class ScopeGraph:
    """
    ScopeGraph 表示整个文件或模块级别的作用域关系图。

    核心设计思想：
    - 每一个作用域、定义、引用、导入语句都作为一个节点（ScopeNode）
    - 不同语义关系通过不同类型的边（EdgeKind）连接
    - 通过 TextRange 判断节点之间的层级（父子作用域）
    """

    def __init__(self, range: TextRange, src_bytes: bytearray = None):
        # 有向图，用于存储所有节点及其关系
        self._graph = DiGraph()
        # 节点自增 ID 计数器
        self._node_counter = 0

        # 作用域 ID -> TextRange 的映射表
        self.scope2range: Dict[ScopeID, TextRange] = {}

        # 创建根作用域节点（通常对应整个文件）
        root_scope = ScopeNode(range=range, type=NodeKind.SCOPE)
        self.root_idx = self.add_node(root_scope)
        self.scope2range[self.root_idx] = range

        # 原始源代码字节（用于 span 反选文本）
        self.src_bytes = src_bytes
        # 无法解析到定义或导入的引用列表
        self.unresolved_refs: List[Reference] = []

    def insert_local_scope(self, new: LocalScope):
        # 根据文本范围查找父作用域
        parent_scope = self.scope_by_range(new.range, self.root_idx)
        if parent_scope is not None:
            # 创建新的作用域节点
            new_node = ScopeNode(range=new.range, type=NodeKind.SCOPE)
            new_id = self.add_node(new_node)
            # 子作用域 -> 父作用域
            self._graph.add_edge(new_id, parent_scope, type=EdgeKind.ScopeToScope)
            self.scope2range[new_id] = new.range

    def insert_local_import(self, new: LocalImportStmt):
        # 导入语句所属的最近作用域
        parent_scope = self.scope_by_range(new.range, self.root_idx)
        if parent_scope is not None:
            # 导入节点保存 from / aliases / names 等语义信息
            new_node = ScopeNode(
                range=new.range,
                type=NodeKind.IMPORT,
                data={
                    "from_name": new.from_name,
                    "aliases": new.aliases,
                    "names": new.names,
                },
            )

            new_id = self.add_node(new_node)
            # Import -> Scope 关系
            self._graph.add_edge(new_id, parent_scope, type=EdgeKind.ImportToScope)

    def insert_local_def(self, new: LocalDef) -> None:
        # 定义所在的最内层作用域
        defining_scope = self.scope_by_range(new.range, self.root_idx)
        if defining_scope is not None:
            # 定义节点（变量 / 函数 / 类等）
            new_def = ScopeNode(
                range=new.range,
                name=new.name,
                type=NodeKind.DEFINITION,
                data={"def_type": new.symbol},
            )
            new_idx = self.add_node(new_def)
            # Definition -> Scope
            self._graph.add_edge(new_idx, defining_scope, type=EdgeKind.DefToScope)

    def insert_hoisted_def(self, new: LocalDef) -> None:
        # 用于“提升（hoist）”定义的场景（如某些语言语义）
        defining_scope = self.scope_by_range(new.range, self.root_idx)
        if defining_scope is not None:
            def_type = new.symbol
            new_def = ScopeNode(
                range=new.range,
                name=new.name,
                type=NodeKind.DEFINITION,
            )
            new_idx = self.add_node(new_def)
            # 查找父作用域，将定义提升至父级
            parent_scope = self.parent_scope(defining_scope)
            target_scope = parent_scope if parent_scope is not None else defining_scope

            self._graph.add_edge(new_idx, target_scope, type=EdgeKind.DefToScope)

    def insert_global_def(self, new: LocalDef) -> None:
        # 全局定义，直接挂载到根作用域
        new_def = ScopeNode(
            range=new.range,
            name=new.name,
            type=NodeKind.DEFINITION,
        )
        new_idx = self.add_node(new_def)
        self._graph.add_edge(new_idx, self.root_idx, type=EdgeKind.DefToScope)

    def insert_ref(self, new: Reference) -> None:
        # 候选定义与导入列表
        possible_defs = []
        possible_imports = []

        # 引用所在的最内层作用域
        local_scope_idx = self.scope_by_range(new.range, self.root_idx)
        if local_scope_idx is not None:
            # 向上遍历作用域栈（词法作用域链）
            for scope in self.parent_scope_stack(local_scope_idx):
                # 查找定义
                for src, dst, attrs in self._graph.in_edges(scope, data=True):
                    if attrs["type"] == EdgeKind.DefToScope:
                        local_def = src
                        def_node = self.get_node(local_def)
                        if def_node.type == NodeKind.DEFINITION:
                            if new.name == def_node.name:
                                possible_defs.append((local_def, def_node.name))
                                break

                                # 查找导入
                for local_import in [
                    src
                    for src, dst, attrs in self._graph.in_edges(scope, data=True)
                    if attrs["type"] == EdgeKind.ImportToScope
                ]:
                    import_node = self.get_node(local_import)
                    if import_node.type == NodeKind.IMPORT:
                        if new.name in import_node.data["names"]:
                            possible_imports.append((local_import, import_node.name))

        if possible_defs or possible_imports:
            # 创建引用节点
            new_ref = ScopeNode(range=new.range, name=new.name, type=NodeKind.REFERENCE)
            ref_idx = self.add_node(new_ref)

            # Reference -> Definition
            for def_idx, _ in possible_defs:
                self._graph.add_edge(ref_idx, def_idx, type=EdgeKind.RefToDef)

            # Reference -> Import
            for imp_idx, _ in possible_imports:
                self._graph.add_edge(ref_idx, imp_idx, type=EdgeKind.RefToImport)

            # Reference -> Origin Scope
            self._graph.add_edge(ref_idx, local_scope_idx, type=EdgeKind.RefToOrigin)
        else:
            # 无法解析的引用
            self.unresolved_refs.append(new)

    def scopes(self) -> List[ScopeID]:
        # 返回所有作用域节点 ID
        return [
            u
            for u, attrs in self._graph.nodes(data=True)
            if attrs["type"] == NodeKind.SCOPE
        ]

    def imports(self, start: int) -> List[int]:
        # 返回某作用域下的所有导入节点
        return [
            u
            for u, v, attrs in self._graph.in_edges(start, data=True)
            if attrs["type"] == EdgeKind.ImportToScope
        ]

    def get_all_imports(self) -> List[ScopeNode]:
        # 获取全图中所有导入节点
        all_imports = []

        scopes = self.scopes()
        for scope in scopes:
            all_imports.extend([self.get_node(i) for i in self.imports(scope)])

        return all_imports

    def definitions(self, start: int) -> List[ScopeNode]:
        # 获取某作用域内的定义节点
        return [
            self.get_node(u)
            for u, v, attrs in self._graph.in_edges(start, data=True)
            if attrs["type"] == EdgeKind.DefToScope
        ]

    def get_all_definitions(self) -> List[ScopeNode]:
        # 获取全图中的所有定义
        all_defs = []

        scopes = self.scopes()
        for scope in scopes:
            all_defs.extend(self.definitions(scope))

        return all_defs

    def references_by_origin(self, start: int) -> List[int]:
        # 获取源自某作用域的所有引用节点
        return [
            u
            for u, v, attrs in self._graph.in_edges(start, data=True)
            if attrs["type"] == EdgeKind.RefToOrigin
        ]

    def child_scopes(self, start: ScopeID) -> List[ScopeID]:
        # 返回某作用域的直接子作用域
        return [
            u
            for u, v, attrs in self._graph.edges(data=True)
            if attrs["type"] == EdgeKind.ScopeToScope and v == start
        ]

    def parent_scope(self, start: ScopeID) -> Optional[ScopeID]:
        # 返回某作用域的直接父作用域
        if self.get_node(start).type == NodeKind.SCOPE:
            for src, dst, attrs in self._graph.out_edges(start, data=True):
                if attrs["type"] == EdgeKind.ScopeToScope:
                    return dst
        return None

    def scope_by_range(self, range: TextRange, start: ScopeID = None) -> ScopeID:
        # 根据文本范围递归定位最内层作用域
        node = self.get_node(start)
        if node.range.contains(range):
            for child_id, attrs in [
                (src, attrs)
                for src, dst, attrs in self._graph.in_edges(start, data=True)
                if attrs["type"] == EdgeKind.ScopeToScope
            ]:
                if child := self.scope_by_range(range, child_id):
                    return child
            return start

        return None

    def range_by_scope(self, scope: ScopeID) -> Optional[TextRange]:
        # 根据作用域 ID 返回对应的文本范围
        return self.scope2range.get(scope, None)

    def child_scope_stack(self, start: ScopeID) -> List[ScopeID]:
        # 返回某作用域的所有后代作用域
        stack = self.child_scopes(start)

        for child in self.child_scopes(start):
            stack += self.child_scope_stack(child)

        return stack

    def get_leaf_children(self, start: ScopeID) -> Iterator[ScopeID]:
        # 获取没有子节点的叶子节点（DFS 后序）
        for node in dfs_postorder_nodes(self._graph, start):
            if self._graph.out_degree(node) == 0:
                yield node

    def parent_scope_stack(self, start: ScopeID):
        # 构造一个向上遍历的作用域栈
        return ScopeStack(self._graph, start)

    def add_node(self, node: ScopeNode) -> int:
        # 向图中添加节点并返回其 ID
        id = self._node_counter
        self._graph.add_node(id, **node.dict())

        self._node_counter += 1

        return id

    def get_node(self, idx: int) -> ScopeNode:
        # 从图中恢复 ScopeNode 对象
        return ScopeNode(**self._graph.nodes(data=True)[idx])

    def find_definition(self, reference: Reference) -> Optional[ScopeNode]:
        # 查找引用对应的定义或导入
        possible_defs = []
        possible_imports = []

        local_scope_idx = self.scope_by_range(reference.range, self.root_idx)
        if local_scope_idx is not None:
            for scope in self.parent_scope_stack(local_scope_idx):
                for local_def in [
                    src
                    for src, dst, attrs in self._graph.in_edges(scope, data=True)
                    if attrs["type"] == EdgeKind.DefToScope
                ]:
                    def_node = self.get_node(local_def)
                    if def_node.type == NodeKind.DEFINITION and def_node.name == reference.name:
                        possible_defs.append(def_node)
                        break

                for local_import in [
                    src
                    for src, dst, attrs in self._graph.in_edges(scope, data=True)
                    if attrs["type"] == EdgeKind.ImportToScope
                ]:
                    import_node = self.get_node(local_import)
                    if import_node.type == NodeKind.IMPORT and reference.name in import_node.data["names"]:
                        possible_imports.append(import_node)

        if possible_defs:
            return possible_defs[0]
        elif possible_imports:
            return possible_imports[0]

        return None

    def find_all_external_references(scope_graph: "ScopeGraph") -> List[ScopeNode]:
        # 查找所有通过 import 间接引用的外部符号
        external_references = []
        all_imports = scope_graph.get_all_imports()
        for import_node in all_imports:
            import_index = import_node.id
            references_to_import = [
                src for src, dst, attrs in scope_graph._graph.in_edges(import_index, data=True)
                if attrs["type"] == EdgeKind.RefToImport
            ]

            for ref_index in references_to_import:
                ref_node = scope_graph.get_node(ref_index)
                external_references.append(ref_node)

        return external_references

    def unresolved_refs_name(self) -> List[str]:
        # 返回所有未解析引用的名称
        return [ref.name for ref in self.unresolved_refs]

    def find_unresolved_refs(self):
        # 预留接口：遍历未解析引用
        for ref in self.unresolved_refs:
            name = ref.name

    def span_select(self, *ranges: List[TextRange], indent=False):
        # 根据 TextRange 从源代码中截取文本
        if not ranges or not all(ranges):
            return ""

        start, end = ranges[0].start_byte, ranges[-1].end_byte
        select = self.src_bytes[start:end].decode("utf-8")
        if indent:
            return " " * ranges[0].start_point[1] + select
        return select

    def to_str(self):
        # 生成整个作用域图的可读字符串表示
        repr = "\n"

        for u, v, attrs in self._graph.edges(data=True):
            edge_type = attrs["type"]
            u_data = ""
            v_data = ""

            u_data = self.get_node(u)
            v_data = self.get_node(v)

            repr += f"Edge: {u}:{u_data.name}({self.span_select(u_data.range)})({u_data.range.start_point}, {u_data.range.end_point}) \
                \n--{edge_type}-> \n{v}:{v_data.name}({self.span_select(v_data.range)})({u_data.range.start_point}, {u_data.range.end_point})\n\n"

        return repr
