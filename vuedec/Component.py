#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from kutil.language.AST import AST, ASTNode
from kutil.language.languages.javascript import nodes
from kutil.language.languages.javascript.syntax import JSNode

from vuedec import JSParser, Files

_TEMPLATE = """<template>
{TEMPLATE}
</template>
<script>
{IMPORTS}

export default {DEFINITION}
</script>"""
_VUE_FUNCTIONS: set[str] = {  # TODO add all
    'normalizeClass', 'computed', 'renderList', 'toDisplayString', 'resolveComponent',
    'createElementBlock', 'defineComponent', 'createBlock', 'createBaseVNode', 'createCommentVNode',
    'createVNode', '_export_sfc', 'ref', 'withCtx', 'openBlock'
}
_VUE_RENDER_ARGUMENTS: list[str] = ["_ctx", "_cache", "$props", "$setup", "$data", "$options"]

__all__ = [
    "Component", "_VUE_RENDER_ARGUMENTS"
]


class Component:
    sourceFile: JSParser
    ast: AST
    moduleNodes: list[ASTNode]
    name: str
    definition: nodes.ObjectExpression  # In future also support the function version
    renderMethod: nodes.FunctionDeclaration
    functionMap: dict[str, str]
    functionReverseMap: dict[str, str]
    mainFileName: str

    vueImports: set[str]
    mainImports: set[str]

    def __init__(self, sourceFile: JSParser, ast: AST, moduleNodes: list[ASTNode],
                 definition: nodes.ObjectExpression,
                 renderMethod: nodes.FunctionDeclaration, functionMap: dict[str, str],
                 functionReverseMap: dict[str, str], mainFileName: str) -> None:
        self.sourceFile = sourceFile
        self.ast = ast
        self.moduleNodes = moduleNodes
        self.name = "<TODO>"  # Extract from definition
        self.definition = definition
        self.renderMethod = renderMethod
        self.functionMap = functionMap
        self.functionReverseMap = functionReverseMap
        self.mainFileName = mainFileName

        self.vueImports = set()
        self.mainImports = set()

    def _traverseFromNode(self, node: nodes.Node):
        # TODO Find a better way to traverse node's children
        for key, val in vars(node).items():
            if key in {"data", "type"}:
                continue

            if isinstance(val, int):
                indexes = [val]
            elif isinstance(val, list):
                indexes = val
            else:
                continue
            for index in indexes:
                try:
                    subNode = self.ast.getNode(index)
                    assert isinstance(subNode, nodes.Node)
                    yield node, subNode  # Parent, child
                    yield from self._traverseFromNode(subNode)
                except IndexError:
                    pass  # Maybe a bad index?

    def mapFunctions(self, node: nodes.Node, isRenderMethod: bool,
                     isInsideRenderMethod: bool = False):
        """
        Changes the function names to their corresponding names in functionMap.
        """
        if isRenderMethod and isInsideRenderMethod:
            raise ValueError("Cannot be a render method while being inside it")

        argMap = {}
        if isRenderMethod:
            assert isinstance(node, nodes.FunctionDeclaration)
            for arg, mapToName in zip(_VUE_RENDER_ARGUMENTS, self.ast.getNodes(node.params)):
                assert isinstance(mapToName, nodes.Identifier)
                argMap[mapToName.name] = arg

        for parent, identifier in self._traverseFromNode(node):
            if identifier.type is JSNode.Identifier:
                assert isinstance(identifier, nodes.Identifier)
                if isRenderMethod and identifier.name in argMap:
                    # Map obfuscated argument names to their readable opposites
                    identifier.name = argMap[identifier.name]

                    if (identifier.name == _VUE_RENDER_ARGUMENTS[0] and
                            parent.type is JSNode.MemberExpression):
                        # Change _ctx.thing to thing (used inside the template)
                        assert isinstance(parent, nodes.StaticMemberExpression)
                        assert not parent.computed and not parent.optionalChain
                        srcProp = self.ast.getNode(parent.property)
                        assert isinstance(srcProp, nodes.Node)
                        self.ast.replaceNode(parent, srcProp.clone())

                    continue
                if (identifier.name not in self.functionReverseMap or
                        parent.type is not JSNode.CallExpression):
                    continue
                # Map imported thing to its index.js local name
                identifier.name = self.functionReverseMap[identifier.name]
                if isRenderMethod or isInsideRenderMethod:
                    continue
                if identifier.name in _VUE_FUNCTIONS:
                    self.vueImports.add(identifier.name)
                else:
                    self.mainImports.add(identifier.name)
        # if saveImports:
        #     print("VUE:", self.vueImports)
        #     print("MAIN:", self.mainImports)

    def findNonMainImports(self) -> list[nodes.Node]:
        from vuedec.VueDecompiler import VueDecompiler

        for node in self.ast.getAllNodes():
            assert isinstance(node, nodes.Node)
            if node.type != JSNode.ImportDeclaration:
                continue
            assert isinstance(node, nodes.ImportDeclaration)

            source = VueDecompiler.absPath(
                VueDecompiler.getLiteralStr(self.ast.getNode(node.source)))
            if source == self.mainFileName:
                continue
            raise NotImplementedError

        return []

    def mapComponents(self, components: nodes.ASTNode) -> list[str]:
        """Maps the component list dict inside the component definition to their names,
        returning a list of imports."""
        imports: list[str] = []

        assert isinstance(components, nodes.ObjectExpression)
        for i, (key, value) in enumerate(components.items(self.ast)):
            if not isinstance(value, nodes.Identifier):
                continue
            if value.name not in self.functionReverseMap:
                componentName = self.sourceFile.findComponentNameByVarName(value.name)
                imports.append(f"import {componentName} from '{componentName}.vue'", )
                value.name = componentName
                continue
            # The component is defined inside the main file
            value.name = self.functionReverseMap[value.name]
            self.mainImports.add(value.name)
        return imports

    def decompile(self, target: Files):
        from vuedec.TemplateParser import TemplateParser

        output = _TEMPLATE

        self.mapFunctions(self.definition, False)
        self.mapFunctions(self.renderMethod, True)

        try:
            componentImports = self.mapComponents(self.definition.getByKey("components", self.ast))
        except KeyError as e:
            print("KeyError (shouldn't occur):", e)
            componentImports = []

        imports: list[str] = [
            f"import {{{', '.join(self.vueImports)}}} from 'vue'",
            f"import {{{', '.join(self.mainImports)}}} from '{self.mainFileName}'",
            *componentImports
        ]
        imports.extend(map(lambda x: x.toString(self.ast), self.findNonMainImports()))
        output = output.replace("{IMPORTS}", "\n".join(imports))

        output = output.replace("{DEFINITION}", self.definition.toString(self.ast))

        templateParser = TemplateParser(self)
        output = output.replace("{TEMPLATE}", templateParser.parse(self.renderMethod))

        target.set(f"{self.extractName()}.vue", output)

    def extractName(self) -> str:
        definition = self.definition.getByKey("name", self.ast)
        assert isinstance(definition, nodes.Literal)
        return definition.value
