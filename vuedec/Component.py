#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from kutil.language.AST import AST, ASTNode
from kutil.language.languages.javascript import nodes

from vuedec import JSParser, Files

_TEMPLATE = """<template>
{TEMPLATE}
</template>
<script>
{IMPORTS}

export default {DEFINITION}
</script>"""


class Component:
    sourceFile: JSParser
    ast: AST
    moduleNodes: list[ASTNode]
    name: str
    definition: nodes.ObjectExpression  # In future also support the function version
    renderMethod: nodes.FunctionDeclaration

    def __init__(self, sourceFile: JSParser, ast: AST, moduleNodes: list[ASTNode],
                 definition: nodes.ObjectExpression,
                 renderMethod: nodes.FunctionDeclaration) -> None:
        self.sourceFile = sourceFile
        self.ast = ast
        self.moduleNodes = moduleNodes
        self.name = "<TODO>"  # Extract from definition
        self.definition = definition
        self.renderMethod = renderMethod

    def decompile(self, target: Files):
        pass
