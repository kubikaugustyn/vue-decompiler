#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import json

from kutil.io import enumFiles
from kutil.language.AST import ASTNode, AST
from kutil.language.languages.javascript import nodes
from kutil.language.languages.javascript.syntax import JSNode

from vuedec.Cache import Cache
from vuedec.Component import Component
from vuedec.DecompilerUI import DecompilerUI, CmdUI
from vuedec.Files import Files
from vuedec.JSParser import JSParser


class VueDecompiler:
    source: Files
    target: Files
    cache: str
    ui: DecompilerUI
    decompiledCache: Cache
    mainFileName: str

    functionMap: dict[str, str]  # index.js --> exported
    functionReversedMap: dict[str, str]  # exported --> index.js

    def __init__(self, source: str, target: str, cache: str):
        self.source = Files(source)
        self.target = Files(target)
        self.cache = cache
        self.decompiledCache = Cache("vue-decompiler", cache)
        self.ui = CmdUI()
        self.mainFileName = "index.js"

        self.functionMap = {}
        self.functionReversedMap = {}

    def set_ui(self, new_ui):
        if not isinstance(new_ui, DecompilerUI):
            raise TypeError("Bad UI class")
        self.ui = new_ui

    def decompile(self):
        f = self.source
        u = self.ui
        if not f.has(self.mainFileName):
            self.mainFileName = u.ask("Enter main file name (note that a bad name may break the"
                                      " code because of import specifier mapping): ")
        i = JSParser(f, self.mainFileName, u, self.cache, immediately_parse=False)
        self.extractFunctionNames(i)
        # print(self.functionMap)
        for other_file_name, _ in enumFiles(f.path, extendedInfo=False):
            assert f.has(other_file_name), f"No such file '{other_file_name}' found"  # Wtf

            if other_file_name == self.mainFileName or not (
                    other_file_name.endswith(".js") and not other_file_name.endswith(
                ".min.js")) or not other_file_name[0].istitle():
                continue

            other_file = JSParser(f, other_file_name, u, self.cache)
            self.decompileFile(other_file)

    def extractFunctionNames(self, indexJS: JSParser):
        c = Cache("vue-decompiler-fn-map", self.cache)

        if c.has("map") and c.has("map-reversed"):
            self.functionMap = c.get("map")
            self.functionReversedMap = c.get("map-reversed")
            return

        indexJS.parse()

        ast: AST = indexJS.ast
        moduleNodes: list[ASTNode] = ast.getNodes(indexJS.entryPoint.body)

        self.functionMap = {}
        self.functionReversedMap = {}
        for export in self.findExports(moduleNodes):
            for spec in ast.getNodes(export.specifiers):
                assert isinstance(spec, nodes.ExportSpecifier)

                localName: str = self.getIdentifierName(
                    ast.getNode(spec.local))  # .partition("$")[0] # I forgot why
                exportedName: str = self.getIdentifierName(ast.getNode(spec.exported))

                assert localName not in self.functionMap
                assert exportedName not in self.functionReversedMap
                self.functionMap[localName] = exportedName
                self.functionReversedMap[exportedName] = localName
        c.set("map", self.functionMap)
        c.set("map-reversed", self.functionReversedMap)
        c.save()

    def extractImportedFunctionNames(self, moduleNodes: list[ASTNode], ast: AST) \
            -> tuple[dict[str, str], dict[str, str]]:
        functionMap = {}  # defineComponent --> v
        functionReversedMap = {}  # v --> defineComponent

        imports = self.findImports(moduleNodes)
        for importNode in imports:
            assert isinstance(importNode, nodes.ImportDeclaration)
            srcName: str = self.getLiteralStr(ast.getNode(importNode.source))
            if self.absPath(srcName) != self.mainFileName:
                continue

            for specifier in ast.getNodes(importNode.specifiers):
                assert isinstance(specifier, nodes.ImportSpecifier)
                # import {importedName as localName, ...} from "..."
                localName: str = self.getIdentifierName(ast.getNode(specifier.local))
                importedName: str = self.getIdentifierName(ast.getNode(specifier.imported))

                assert localName not in functionReversedMap
                assert importedName in self.functionReversedMap

                mappedImportedFunction = self.functionReversedMap[importedName]
                assert mappedImportedFunction not in functionMap

                functionMap[mappedImportedFunction] = localName
                functionReversedMap[localName] = mappedImportedFunction

        return functionMap, functionReversedMap

    @staticmethod
    def absPath(path: str) -> str:
        # Maybe there's a better way to do it
        if path.startswith("./"):
            return path[2:]
        return path

    @staticmethod
    def findExports(moduleNodes: list[ASTNode]) -> list[nodes.ExportNamedDeclaration]:
        return list(filter(lambda node: node.type is JSNode.ExportNamedDeclaration, moduleNodes))

    @staticmethod
    def findImports(moduleNodes: list[ASTNode]) -> list[nodes.ImportDeclaration]:
        return list(filter(lambda node: node.type is JSNode.ImportDeclaration, moduleNodes))

    def findVarDeclarator(self, name: str, moduleNodes: list[ASTNode],
                          ast: AST) -> nodes.VariableDeclarator:
        for node in moduleNodes:
            if node.type is JSNode.VariableDeclaration:
                assert isinstance(node, nodes.VariableDeclaration)
                for declarator in ast.getNodes(node.declarations):
                    assert isinstance(declarator, nodes.VariableDeclarator)
                    cmpName = self.getIdentifierName(ast.getNode(declarator.id))
                    if cmpName == name:
                        return declarator

        raise KeyError(f"Variable {name} declaration not found")

    def findMethodDeclarator(self, name: str, moduleNodes: list[ASTNode],
                             ast: AST) -> nodes.FunctionDeclaration:
        for node in moduleNodes:
            if node.type is JSNode.FunctionDeclaration:
                assert isinstance(node, nodes.FunctionDeclaration)

                cmpName = self.getIdentifierName(ast.getNode(node.id))
                if cmpName == name:
                    return node

        raise KeyError(f"Function {name} declaration not found")

    def findMethodCall(self, returnToVarName: str, moduleNodes: list[ASTNode],
                       ast: AST) -> nodes.CallExpression:
        var = self.findVarDeclarator(returnToVarName, moduleNodes, ast)
        call = ast.getNode(var.init)
        assert isinstance(call, nodes.CallExpression)
        return call

    def findComponentDefinitions(self, knownName: str, moduleNodes: list[ASTNode], ast: AST,
                                 fnMap: dict[str, str], fnReverseMap: dict[str, str],
                                 srcFile: JSParser) \
            -> tuple[Component, list[Component]]:
        returnKnown: Component | None = None
        returnOthers: list[Component] = []
        componentByName: dict[str, Component] = {}

        for node in moduleNodes:
            if node.type is JSNode.VariableDeclaration:
                assert isinstance(node, nodes.VariableDeclaration)
                for declarator in ast.getNodes(node.declarations):
                    assert isinstance(declarator, nodes.VariableDeclarator)
                    cmpName = self.getIdentifierName(ast.getNode(declarator.id))

                    if declarator.init is None:
                        continue

                    componentVarInit = ast.getNode(declarator.init)
                    if not isinstance(componentVarInit, nodes.CallExpression):
                        continue

                    callee = ast.getNode(componentVarInit.callee)

                    if not isinstance(callee, nodes.Identifier):
                        continue
                    print(callee.name, fnMap.get(callee.name))
                    # TODO Fix

                    if self.isIdentifierName(callee,
                                             "_export_sfc",
                                             fnMap):
                        definitionName = self.getIdentifierName(
                            ast.getNode(componentVarInit.arguments[0]))
                        infoList = ast.getNode(componentVarInit.arguments[1])
                        assert isinstance(infoList, nodes.ArrayExpression)
                        renderList = ast.getNode(infoList.elements[0])
                        assert isinstance(renderList, nodes.ArrayExpression)
                        assert self.getLiteralStr(ast.getNode(renderList.elements[0]))
                        renderFnName = self.getIdentifierName(ast.getNode(renderList.elements[1]))

                        try:
                            cmpDefinitionCall = self.findMethodCall(definitionName, moduleNodes,
                                                                    ast)
                        except AssertionError:
                            cmpDefinitionCall = None
                    else:
                        cmpDefinitionCall = componentVarInit

                        if not self.isIdentifierName(ast.getNode(cmpDefinitionCall.callee),
                                                     "defineComponent", fnMap):
                            continue

                        renderFnName = None

                    if cmpDefinitionCall is not None:
                        assert self.isIdentifierName(ast.getNode(cmpDefinitionCall.callee),
                                                     "defineComponent", fnMap)
                        cmpDefinition = ast.getNode(cmpDefinitionCall.arguments[0])
                        assert isinstance(cmpDefinition, nodes.ObjectExpression)
                    else:
                        cmpDefinition = None

                    renderMethod = self.findMethodDeclarator(renderFnName, moduleNodes,
                                                             ast) if renderFnName else None

                    cmp: Component = Component(srcFile, ast, moduleNodes, cmpDefinition,
                                               renderMethod, fnMap, fnReverseMap, self.mainFileName)

                    componentName = cmp.extractName()
                    if componentName in componentByName:
                        # Unregister the component
                        # Basically, defineComponent is considered a component
                        # before _export_sfc occurs, tricking the program into
                        # thinking there were 2 components of such name
                        if componentByName[componentName] in returnOthers:
                            returnOthers.remove(componentByName[componentName])
                        srcFile.unregisterComponent(componentName)
                    componentByName[componentName] = cmp
                    srcFile.registerComponent(cmp, componentName, cmpName,
                                              declarator)

                    if cmpName == knownName:
                        returnKnown = cmp
                    else:
                        returnOthers.append(cmp)
        if returnKnown is None:
            raise KeyError(f"Component '{knownName}' declaration not found")

        return returnKnown, returnOthers

    @staticmethod
    def getIdentifierName(identifier: nodes.ASTNode) -> str:
        assert isinstance(identifier, nodes.Identifier)
        return identifier.name

    @staticmethod
    def getLiteralStr(literal: nodes.ASTNode) -> str:
        assert isinstance(literal, nodes.Literal)
        return literal.value

    def isIdentifierName(self, identifier: nodes.ASTNode, name: str,
                         fnMap: dict | None = None) -> bool:
        if fnMap is None:
            fnMap = self.functionMap

        if name not in fnMap:
            # TODO THE FRICKING FUNCTION NAMES ARE OBFUSCATED TOO NOW EVEN WITHIN THE index.js FILE
            return False
        cmpName = self.getIdentifierName(identifier)
        return cmpName == fnMap[name]

    def decompileFile(self, parser: JSParser) -> str:
        assert parser.ast is not None and parser.entryPoint is not None
        if self.decompiledCache.has(parser.file_name):
            return self.decompiledCache.get(parser.file_name)

        print(f"Decompiling {parser.file_name}", end="")

        ast = parser.ast
        module = parser.entryPoint
        moduleNodes = ast.getNodes(module.body)

        # Map the functions
        fnMap, fnReverseMap = self.extractImportedFunctionNames(moduleNodes, ast)

        # Find the component var name
        export = self.findExports(moduleNodes)[0]
        spec: ASTNode = ast.getNode(export.specifiers[0])
        assert isinstance(spec, nodes.ExportSpecifier)
        componentVarName = self.getIdentifierName(ast.getNode(spec.local))
        # print(componentVarName)

        mainComponent, otherComponents = self.findComponentDefinitions(componentVarName,
                                                                       moduleNodes, ast, fnMap,
                                                                       fnReverseMap,
                                                                       parser)
        componentNames = [mainComponent.extractName()]

        mainComponent.decompile(self.target)
        for other in otherComponents:
            other.decompile(self.target)
            componentNames.append(other.extractName())
        print(f" - DONE (components: {', '.join(componentNames)})")
