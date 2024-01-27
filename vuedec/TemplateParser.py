#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from kutil.language.AST import AST
from kutil.language.languages.javascript import nodes

from vuedec import JSParser
from vuedec.Component import Component
from vuedec.VueDecompiler import VueDecompiler


class TemplateParser:
    component: Component
    ast: AST
    sourceFile: JSParser

    usedComponentsPool: dict[str, str]  # varName --> component name

    def __init__(self, component: Component):
        self.component = component
        self.ast = component.ast
        self.sourceFile = component.sourceFile

        self.usedComponentsPool = {}

    def extractUsedComponents(self, varDeclaration: nodes.VariableDeclaration):
        for declaratorI in varDeclaration.declarations:
            declarator = self.ast.getNode(declaratorI)
            assert isinstance(declarator, nodes.VariableDeclarator)
            cmpVarName = VueDecompiler.getIdentifierName(self.ast.getNode(declarator.id))
            call = self.ast.getNode(declarator.init)
            assert isinstance(call, nodes.CallExpression)
            assert VueDecompiler.getIdentifierName(
                self.ast.getNode(call.callee)) == "resolveComponent"
            cmpName = VueDecompiler.getLiteralStr(self.ast.getNode(call.arguments[0]))
            self.usedComponentsPool[cmpVarName] = cmpName

    def parseTemplate(self, node: nodes.Node) -> str:
        """Converts a template node into it's string representation."""
        return "SUS" # TODO

    def parse(self, renderMethod: nodes.FunctionDeclaration) -> str:
        body = self.ast.getNode(renderMethod.body)
        assert isinstance(body, nodes.BlockStatement)
        assert len(body.body) == 2  # resolveComponent(s) + return
        varDeclaration = self.ast.getNode(body.body[0])
        assert isinstance(varDeclaration, nodes.VariableDeclaration)
        self.extractUsedComponents(varDeclaration)
        returnStatement = self.ast.getNode(body.body[1])
        assert isinstance(returnStatement, nodes.ReturnStatement)
        returnThing = self.ast.getNode(returnStatement.argument)
        assert isinstance(returnThing, nodes.SequenceExpression)
        return self.parseTemplate(returnThing)
