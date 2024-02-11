#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import random

from kutil import NL
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
    renderMethod: nodes.FunctionDeclaration | None
    functionMap: dict[str, str]
    functionReverseMap: dict[str, str]
    mainFileName: str
    componentName: str | None

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
        self.componentName = None

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

        # if self.extractName() == "AdminMarkdownModule":
        #     pass

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
                # TODO What if {thing: au} is outside the components definition?
                if (identifier.name not in self.functionReverseMap or
                        parent.type not in (JSNode.CallExpression, JSNode.Property)):
                    # Either call - createBaseVNode, or property - components: {Button: au}
                    continue
                if parent.type is JSNode.Property:
                    assert isinstance(parent, nodes.Property)
                    if self.ast.getNode(parent.value) != identifier:
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

    def findAllImports(self) -> list[nodes.Node]:
        allImports = []

        for node in self.ast.getAllNodes():
            assert isinstance(node, nodes.Node)
            if node.type != JSNode.ImportDeclaration:
                continue
            assert isinstance(node, nodes.ImportDeclaration)

            allImports.append(node)

        return allImports

    def mapComponents(self, components: nodes.ASTNode) -> list[str]:
        """Maps the component list dict inside the component definition to their names,
        returning a list of imports."""
        imports: list[str] = []

        assert isinstance(components, nodes.ObjectExpression)
        for i, (key, value) in enumerate(components.items(self.ast)):
            if not isinstance(value, nodes.Identifier):
                continue
            if not isinstance(key, nodes.Identifier):
                continue
            if value.name not in self.functionReverseMap:
                if value.name in self.mainImports or value.name in self.vueImports:
                    continue
                try:
                    componentName = self.sourceFile.findComponentNameByVarName(value.name, key.name)
                    imports.append(f"import {componentName} from './{componentName}.vue'")
                    value.name = componentName
                except KeyError:
                    try:
                        componentName, originalImport = self.sourceFile.findComponentNameByImport(
                            value.name, key.name)
                        imports.append(f"import {componentName} from './{componentName}.vue'"
                                       f" /*{originalImport}*/")
                        value.name = componentName
                    except KeyError:
                        rndName = self.randomUnknownComponentName()
                        imports.append(f"import {rndName} from './{rndName}.vue' /*Unknown,"
                                       f" renamed from {key.name} as {value.name}*/")
                        value.name = rndName
                continue
            # The component is defined inside the main file
            value.name = self.functionReverseMap[value.name]
            self.mainImports.add(value.name)

        return imports

    def decompile(self, target: Files):
        from vuedec.TemplateParser import TemplateParser

        if target.has(f"{self.extractName()}.vue"):
            raise RuntimeError(f"Component '{self.extractName()}' already decompiled")

        output = _TEMPLATE

        if self.definition:
            self.mapFunctions(self.definition, False)
        if self.renderMethod:
            self.mapFunctions(self.renderMethod, True)

        try:
            componentImports = self.mapComponents(self.definition.getByKey("components", self.ast))
        except (KeyError, AttributeError):  # as e:
            # No components
            # print("KeyError (shouldn't occur):", e)
            componentImports = []

        imports: list[str] = []
        if len(self.vueImports) > 0:
            imports.append(f"import {{{', '.join(self.vueImports)}}} from 'vue'")
        if len(self.mainImports) > 0:
            imports.append(f"import {{{', '.join(self.mainImports)}}} from '{self.mainFileName}'")
        imports.extend(componentImports)

        imports.append(f"/*Original imports, might help you find the"
                       f" needed variables that are  being imported*/{NL}/*")
        imports.extend(map(lambda x: x.toString(self.ast), self.findAllImports()))
        imports.append("*/")

        output = output.replace("{IMPORTS}", NL.join(imports))

        if self.definition:
            output = output.replace("{DEFINITION}", self.definition.toString(self.ast))
        else:
            output = output.replace("{DEFINITION}", "/*<NO DEFINITION>*/")

        if self.renderMethod:
            templateParser = TemplateParser(self)
            output = output.replace("{TEMPLATE}", templateParser.parse(self.renderMethod))
        else:
            # TODO Extract the render method from setup()
            output = output.replace("{TEMPLATE}",
                                    "<NO RENDER METHOD, see SETUP's return for it maybe?>")

        target.set(f"{self.extractName()}.vue", output)

    def extractName(self) -> str:
        if self.componentName is not None:
            return self.componentName

        try:
            definition = self.definition.getByKey("name", self.ast)
            assert isinstance(definition, nodes.Literal)
            self.componentName = definition.value
        except (KeyError, AttributeError):
            # print(f"Component name not found, using UnknownName instead")
            self.componentName = self.randomUnknownComponentName()
        return self.componentName

    @staticmethod
    def randomUnknownComponentName() -> str:
        return f"UnknownName_{hex(random.randint(0, 0xffffffff))[2:]}"
