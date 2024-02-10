#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import json
from typing import Any

from kutil import NL
from kutil.language.AST import AST
from kutil.language.languages.javascript import nodes
from kutil.language.languages.javascript.character import TABULATOR
from kutil.language.languages.javascript.syntax import JSNode

from vuedec import JSParser
from vuedec.Component import Component
from vuedec.VueDecompiler import VueDecompiler

__all__ = ["TemplateParser"]

BASE_V_NODE_ARGS: list[str] = ["type", "props", "children", "patchFlag", "dynamicProps",
                               "shapeFlag", "unknown1", "unknown2"]


class BVARGS:  # Base VNode Args
    TYPE: str = BASE_V_NODE_ARGS[0]
    PROPS: str = BASE_V_NODE_ARGS[1]
    CHILDREN: str = BASE_V_NODE_ARGS[2]
    PATCH_FLAG: str = BASE_V_NODE_ARGS[3]
    DYNAMIC_PROPS: str = BASE_V_NODE_ARGS[4]
    SHAPE_FLAG: str = BASE_V_NODE_ARGS[5]
    UNKNOWN1: str = BASE_V_NODE_ARGS[6]
    UNKNOWN2: str = BASE_V_NODE_ARGS[7]


BASE_V_NODE_FALLBACK_PARAMS: dict[str, Any] = {
    BVARGS.PROPS: None,
    BVARGS.CHILDREN: None,
    BVARGS.PATCH_FLAG: 0,
    BVARGS.DYNAMIC_PROPS: None,
    BVARGS.SHAPE_FLAG: 0 if () else 1,
    BVARGS.UNKNOWN1: False,
    BVARGS.UNKNOWN2: False
}

V_NODE_ARGS: list[str] = ["type", "props", "children", "patchFlag", "dynamicProps", "unknown1"]


class VARGS:  # VNode Args
    TYPE: str = V_NODE_ARGS[0]
    PROPS: str = V_NODE_ARGS[1]
    CHILDREN: str = V_NODE_ARGS[2]
    PATCH_FLAG: str = V_NODE_ARGS[3]
    DYNAMIC_PROPS: str = V_NODE_ARGS[4]
    UNKNOWN1: str = V_NODE_ARGS[5]


V_NODE_FALLBACK_PARAMS: dict[str, Any] = {
    VARGS.PROPS: None,
    VARGS.CHILDREN: None,
    VARGS.PATCH_FLAG: 0,
    VARGS.DYNAMIC_PROPS: None,
    VARGS.UNKNOWN1: False
}

STATIC_V_NODE_ARGS: list[str] = ["children", "staticCount"]


class S_VARGS:  # VNode Args
    CHILDREN: str = V_NODE_ARGS[0]
    STATIC_COUNT: str = V_NODE_ARGS[1]


STATIC_V_NODE_FALLBACK_PARAMS: dict[str, Any] = {
    S_VARGS.CHILDREN: None,
    S_VARGS.STATIC_COUNT: None
}

BASE_VUE_COMPONENTS: dict[str, str] = {"Fragment": "template", "Transition": "Transition",
                                       "Static": "template", "Suspense": "Suspense"}
# TODO implement it properly
OPTIONAL_LINE_WRAP: int = 50  # Chars
# https://developer.mozilla.org/en-US/docs/Glossary/Void_element
VOID_ELEMENTS: set[str] = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                           "meta", "param", "source", "track", "wbr"}


class TemplateParser:
    component: Component
    ast: AST
    sourceFile: JSParser

    varPool: dict[str, nodes.Node]
    usedComponentsPool: dict[str, str]  # varName --> component name
    blockStack: list[list | None]
    currentBlock: list | None
    offsetCount: int
    ctxVForCount: int

    def __init__(self, component: Component):
        self.component = component
        self.ast = component.ast
        self.sourceFile = component.sourceFile

        self.usedComponentsPool = {}
        self.varPool = {}
        self.blockStack = []
        self.currentBlock = None
        self.offsetCount = 0
        self.ctxVForCount = 0

    # Helper methods
    def extractUsedComponents(self, varDeclaration: nodes.VariableDeclaration):
        for declaratorI in varDeclaration.declarations:
            declarator = self.ast.getNode(declaratorI)
            assert isinstance(declarator, nodes.VariableDeclarator)
            cmpVarName = VueDecompiler.getIdentifierName(self.ast.getNode(declarator.id))
            call = self.ast.getNode(declarator.init)
            if not isinstance(call, nodes.CallExpression):
                continue
            if VueDecompiler.getIdentifierName(self.ast.getNode(call.callee)) != "resolveComponent":
                continue
            cmpName = VueDecompiler.getLiteralStr(self.ast.getNode(call.arguments[0]))

            assert cmpVarName not in BASE_VUE_COMPONENTS, f"{cmpVarName} is a Vue component name"
            assert cmpName not in BASE_VUE_COMPONENTS.values(), f"{cmpName} is a Vue component"

            self.usedComponentsPool[cmpVarName] = cmpName

    def getParamsFromFnCall(self, fnCall: nodes.CallExpression, paramNames: list[str],
                            paramOverrides: dict[str, Any] | None = None,
                            fallbackParams: dict[str, Any] | None = None) -> dict[str, Any]:
        if paramOverrides is None:
            paramOverrides = {}
        params = fallbackParams.copy() if fallbackParams is not None else {}
        for paramName, paramVal in zip(paramNames, self.ast.getNodes(fnCall.arguments)):
            # Nope v
            # if isinstance(paramVal, nodes.StaticNode) and paramVal.isStatic(self.ast):
            #     params[paramName] = paramVal.toData(self.ast)
            # else:
            params[paramName] = paramVal
        params.update(paramOverrides)
        return params

    def extractVarPool(self) -> dict[str, nodes.Node]:
        varPool = {}

        for node in self.ast.getNodes(self.sourceFile.entryPoint.body):
            if node.type is JSNode.VariableDeclaration:
                assert isinstance(node, nodes.VariableDeclaration)
                for declarator in self.ast.getNodes(node.declarations):
                    assert isinstance(declarator, nodes.VariableDeclarator)
                    varName = VueDecompiler.getIdentifierName(self.ast.getNode(declarator.id))

                    initI: int | None = declarator.init
                    if initI is None:
                        continue

                    init = self.ast.getNode(initI)
                    assert isinstance(init, nodes.Node)

                    varPool[varName] = init
        return varPool

    @property
    def offset(self) -> str:
        return self.offsetCount * TABULATOR
        # info = ""
        # for block in self.blockStack:
        #     info += "N" if block is None else "L"
        # return info

    def tab(self):
        self.offsetCount += 1

    def unTab(self):
        self.offsetCount -= 1
        if self.offsetCount < 0:
            raise ValueError("Offset cannot be negative")

    def openBlock(self, what: bool):
        self.currentBlock = None if what else []
        self.blockStack.append(self.currentBlock)

    def closeBlock(self):
        self.blockStack.pop()
        if len(self.blockStack) == 0:
            self.currentBlock = None
        else:
            self.currentBlock = self.blockStack[-1]

    def setupBlock(self, thing: str) -> str:
        self.closeBlock()
        if self.currentBlock is not None:
            self.currentBlock.append(thing)
        return thing

    @staticmethod
    def surroundString(inp: str) -> str:
        if len(inp) > 2 and inp.startswith('"') and inp.endswith('"') and '"' not in inp[1:-1]:
            return inp
        return '"' + inp.replace('"', "'") + '"'

    def parseNormalizeClass(self, node: nodes.CallExpression) -> tuple[str, dict[str, Any] | None]:
        assert len(node.arguments) == 1
        toNormalize: nodes.Node = nodes.getAstNode(self.ast, node.arguments[0])
        if isinstance(toNormalize, nodes.Literal):
            return toNormalize.raw, None

        normalizeDynamic: list[str] = []
        normalizeStatic: list[str] = []

        if isinstance(toNormalize, nodes.ArrayExpression):
            for item in self.ast.getNodes(toNormalize.elements):
                if isinstance(item, nodes.Literal):
                    normalizeStatic.append(item.raw)
                else:
                    assert isinstance(item, nodes.Node)
                    normalizeDynamic.append(item.toString(self.ast, self.offset, False))
        else:
            normalizeDynamic.append(toNormalize.toString(self.ast, self.offset, False))

        staticString: str = self.surroundString(" ".join(normalizeStatic))
        dynamicString: str | None = None
        if len(normalizeDynamic) > 0:
            if len(normalizeDynamic) == 1:
                dynamicString = self.surroundString(normalizeDynamic[0])
            else:
                dynamicString = self.surroundString('[' + ", ".join(normalizeDynamic) + ']')

        return staticString, {":class": dynamicString} if dynamicString else None

    def parseNormalizeStyle(self, node: nodes.CallExpression) -> tuple[str, dict[str, Any] | None]:
        # TODO Normalize style
        return '"NORMALIZE STYLE"', None

    def parseMethodHandler(self, node: nodes.BinaryExpression) -> str | None:
        # _cache[0] || _cache[0] = <method>

        second = self.ast.getNode(node.right)
        if not isinstance(second, nodes.AssignmentExpression) or second.operator != "=":
            return None
        method = nodes.getAstNode(self.ast, second.right)

        return method.toString(self.ast, self.offset, False)

    def parseAttributeCall(self, node: nodes.Node) -> tuple[str | None, dict[str, Any] | None]:
        if isinstance(node, nodes.CallExpression):
            callee = self.ast.getNode(node.callee)
            if not isinstance(callee, nodes.Identifier):
                return None, None
            name = VueDecompiler.getIdentifierName(callee)
            if name == "normalizeStyle":
                return self.parseNormalizeStyle(node)
            elif name == "normalizeClass":
                return self.parseNormalizeClass(node)
        elif isinstance(node, nodes.BinaryExpression):
            if node.operator == "||":
                return self.parseMethodHandler(node), None
        return None, None

    def parseSlots(self, node: nodes.ObjectExpression) -> str | None:
        # TODO Deal better with only the default slot
        # TODO Fix the offsets
        # <template v-slot:default /> - nope
        # <template #slotId /> - yes
        slots: list[str] = []

        defaultSlot: str | None = None

        for key, value in node.items(self.ast):
            if isinstance(key, nodes.Identifier):
                slotName = key.name
            elif isinstance(key, nodes.Literal):
                slotName = str(key.value)
            else:
                raise ValueError(
                    f"Slot name must be an identifier or literal, not {type(key).__name__}")

            if slotName == "_":
                continue

            if slotName == "default":
                slotBodyWithoutOffset = self.parseTemplate(value)
                defaultSlot = slotBodyWithoutOffset

            self.tab()
            slotBody = self.parseTemplate(value)
            self.unTab()

            slots.append(f"<template #{slotName}>{NL}{slotBody}{NL}{self.offset}</template>")

        if len(slots) == 0:
            raise ValueError("There must be at least 1 slot")

        if len(slots) == 1 and defaultSlot is not None:
            # assert defaultSlot is not None, "The only slot isn't the 'default' slot"
            return defaultSlot

        return NL.join(slots)

    @staticmethod
    def offsetStringBy(string: str, off: str) -> str:
        return NL.join(map(lambda line: off + line, string.split(NL)))

    def parseAttributeToString(self, name: str, value: str | nodes.Node, attributeList: list[str],
                               dynProps: list[str] | None = None) -> None:
        if value is None:
            attributeList.append(name)
            return

        isAsString = False

        if isinstance(value, nodes.Node):
            # TODO Add all values
            # TODO For some reason :onClick appears inside renderList
            isAsString = value.type in {JSNode.Literal} or name in {"onClick"}

            valueStr, additionalAttributes = self.parseAttributeCall(value)
            if additionalAttributes is not None:
                # Used by normalizeStyle and normalizeClass in order to add new attributes
                for key, val in additionalAttributes.items():
                    self.parseAttributeToString(key, val, attributeList, dynProps)
            if valueStr is None:
                if isinstance(value, nodes.StaticNode):
                    valueStr = str(value.toDataOrString(self.ast)).strip()
                else:
                    valueStr = value.toString(self.ast, self.offset, False)

            if not valueStr.startswith('"') and not valueStr.endswith('"'):
                if not isAsString:
                    name = ":" + name
                valueStr = self.surroundString(valueStr)
        else:
            valueStr = value

        if not valueStr or valueStr == '""':
            # TODO Fix attributes such as "disabled"
            return

        isDynamic = dynProps is not None and name in dynProps
        if isAsString and self.ctxVForCount > 0:
            # Patch :onClick within v-for
            isDynamic = False

        attributeList.append(f"{':' if isDynamic else ''}{name}={self.surroundString(valueStr)}")

    # Vue method parsing
    def parseCreateBaseVNode(self, node: nodes.CallExpression,
                             paramOverrides: dict[str, Any] | None = None,
                             addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: type, props, children, patchFlag,
        # dynamicProps, shapeFlag, unknown1, unknown2
        if addAttributes is None:
            addAttributes = {}
        params = self.getParamsFromFnCall(node, BASE_V_NODE_ARGS,
                                          paramOverrides,
                                          BASE_V_NODE_FALLBACK_PARAMS)
        nodeType: str | nodes.Identifier = params[BVARGS.TYPE]
        childrenList: (nodes.ArrayExpression | nodes.CallExpression | nodes.Identifier |
                       nodes.StaticNode | None) = params[BVARGS.CHILDREN]
        props: dict[Any, Any] | nodes.ObjectExpression | nodes.Identifier | None = params[
            BVARGS.PROPS]
        dynProps: list[str] | nodes.ArrayExpression | nodes.Identifier | None = params[
            BVARGS.DYNAMIC_PROPS]

        off: str = self.offset
        children: str | None = None

        attributeList: list[str] = []
        for paramName, value in addAttributes.items():
            self.parseAttributeToString(paramName, value, attributeList)

        if dynProps is not None:
            if isinstance(dynProps, nodes.Identifier):
                dynPropsVarValue = self.varPool[VueDecompiler.getIdentifierName(dynProps)]
                assert isinstance(dynPropsVarValue, nodes.ArrayExpression)
                dynProps = dynPropsVarValue
            if isinstance(dynProps, nodes.ArrayExpression):
                dynProps = dynProps.toData(self.ast)
            assert all(map(lambda x: isinstance(x, str),
                           dynProps)), "Dynamic property list is not full of strings"

        if props is not None:
            if isinstance(props, nodes.Identifier):
                dynPropsVarValue = self.varPool[VueDecompiler.getIdentifierName(props)]
                assert isinstance(dynPropsVarValue, nodes.ObjectExpression)
                props = dynPropsVarValue

            if (isinstance(props, nodes.StaticNode) and
                    not isinstance(props, nodes.ObjectExpression)):
                props = props.toData(self.ast)
        if props is not None:
            assert isinstance(props, nodes.ObjectExpression)
            for key, value in props.items(self.ast):
                if isinstance(key, nodes.StaticNode):
                    keyStr = key.toDataOrString(self.ast, self.offset, False)
                else:
                    keyStr = key.toString(self.ast, self.offset, False)

                self.parseAttributeToString(keyStr, value, attributeList, dynProps)

        attributeList = list(map(
            lambda x: "".join(map(lambda line: line.strip(), x.split(NL))) if x.count(
                NL) < 3 else x,
            attributeList
        ))

        attributes: str | None = (" " + " ".join(attributeList)) if len(attributeList) > 0 else ""

        if childrenList is not None:
            self.tab()
            string = None

            if isinstance(childrenList, nodes.Identifier):
                childrenVarValue = self.varPool[VueDecompiler.getIdentifierName(childrenList)]
                assert isinstance(childrenVarValue,
                                  (nodes.ArrayExpression, nodes.CallExpression, nodes.StaticNode))
                childrenList = childrenVarValue

            if isinstance(childrenList, nodes.ObjectExpression):
                # Slot definition - https://vuejs.org/guide/components/slots.html
                string = self.parseSlots(childrenList)
            elif isinstance(childrenList, nodes.Literal) and childrenList.value is None:
                # 'null'
                string = None
                children = None
            elif (isinstance(childrenList, nodes.StaticNode) and
                  not isinstance(childrenList, nodes.ArrayExpression)):
                string = off + TABULATOR + str(childrenList.toData(self.ast)).strip()
            elif isinstance(childrenList, nodes.CallExpression):
                string = self.parseTemplate(childrenList)

            if isinstance(childrenList, nodes.ArrayExpression):
                childStrs = []
                for child in self.ast.getNodes(childrenList.elements):
                    assert isinstance(child, nodes.Node)
                    if isinstance(child, nodes.StaticNode):
                        childStrs.append(child.toDataStr(self.ast))
                    else:
                        childStrs.append(self.parseTemplate(child))
                children = NL.join(childStrs)
            elif string is not None:
                if len(string) < OPTIONAL_LINE_WRAP and NL not in string:
                    children = string.strip()
                else:
                    children = string
            self.unTab()

            if children is not None and children.endswith(NL):
                children = children[:-len(NL)]
        if isinstance(nodeType, nodes.Identifier):
            # Identifier name, if found, rename
            if nodeType.name in BASE_VUE_COMPONENTS:
                nodeType = BASE_VUE_COMPONENTS[nodeType.name]
            else:
                nodeType = self.usedComponentsPool[nodeType.name]
        elif not isinstance(nodeType, str):
            assert isinstance(nodeType, nodes.StaticNode)
            nodeType = nodeType.toData(self.ast)

        if nodeType in VOID_ELEMENTS and children is not None:
            raise ValueError(f"Void element {nodeType} cannot have children")

        body: str = f"{NL}{children or ''}{NL}{off}"
        if (children is not None and
                len(children) < OPTIONAL_LINE_WRAP and
                NL not in children):
            body = children.strip()

        if children is None:
            return f"{off}<{nodeType}{attributes}{'' if nodeType in VOID_ELEMENTS else ' /'}>"
        return f"{off}<{nodeType}{attributes}>{body}</{nodeType}>"

    def parseCreateVNode(self, node: nodes.CallExpression,
                         addAttributes: dict[str, Any] | None = None,
                         paramOverrides: dict[str, Any] | None = None) -> str:
        # Params as following: type, props, children, patchFlag, dynamicProps, unknown1
        # return createBaseVNode(type, props, children, patchFlag, dynamicProps, <not an argument>,
        #   unknown1, true)
        params = self.getParamsFromFnCall(node, V_NODE_ARGS,
                                          paramOverrides,
                                          V_NODE_FALLBACK_PARAMS)
        # This is to make sure the params provided won't be overwritten
        newNode = nodes.CallExpression(node.callee, [])
        shapeFlag: int = 0

        # TODO Maybe determine the shape flag properly, or totally ignore it?
        """
        nodeType: str | nodes.Identifier = params[VARGS.TYPE]  # TODO DRY
        if isinstance(nodeType, nodes.Identifier):
            # Identifier name, if found, rename
            if nodeType.name in BASE_VUE_COMPONENTS:
                nodeType = BASE_VUE_COMPONENTS[nodeType.name]
            else:
                nodeType = self.usedComponentsPool[nodeType.name]
        elif isinstance(nodeType, str):
            shapeFlag = 1
        else:
            assert isinstance(nodeType, nodes.StaticNode)
            nodeType = nodeType.toData(self.ast)"""

        return self.parseCreateBaseVNode(newNode, {
            BVARGS.TYPE: params[VARGS.TYPE],  # nodeType,
            BVARGS.PROPS: params[VARGS.PROPS],
            BVARGS.CHILDREN: params[VARGS.CHILDREN],
            BVARGS.PATCH_FLAG: params[VARGS.PATCH_FLAG],
            BVARGS.DYNAMIC_PROPS: params[VARGS.DYNAMIC_PROPS],
            BVARGS.SHAPE_FLAG: shapeFlag,
            BVARGS.UNKNOWN1: params[VARGS.UNKNOWN1],
            BVARGS.UNKNOWN2: True,
        }, addAttributes)

    def parseCreateStaticVNode(self, node: nodes.CallExpression,
                               addAttributes: dict[str, Any] | None = None,
                               paramOverrides: dict[str, Any] | None = None) -> str:
        # Params as following: type, props, children, staticCount
        # function createStaticVNode(e, t) {
        #     const r = createVNode(Static, null, e);
        #     return r.staticCount = t, r
        # }
        params = self.getParamsFromFnCall(node, STATIC_V_NODE_ARGS,
                                          paramOverrides,
                                          STATIC_V_NODE_FALLBACK_PARAMS)
        # This is to make sure the params provided won't be overwritten
        newNode = nodes.CallExpression(node.callee, [])

        return self.parseCreateVNode(newNode, addAttributes, {
            VARGS.TYPE: "Static",  # nodeType,
            VARGS.PROPS: None,
            VARGS.CHILDREN: params[S_VARGS.CHILDREN]
        })

    def parseCreateTextVNode(self, node: nodes.CallExpression) -> str:
        assert len(node.arguments) <= 2

        if len(node.arguments) == 0:
            string = '" "'
        else:
            textNode = nodes.getAstNode(self.ast, node.arguments[0])
            string = textNode.toString(self.ast, self.offset, False)

        if string.startswith('"') and string.endswith('"'):
            return self.offset + string[1:-1]
        return f"{self.offset}{{{string}}}"

    def parseCreateElementBlock(self, node: nodes.CallExpression,
                                addAttributes: dict[str, Any] | None = None) -> str:
        assert len(node.arguments) <= 6
        return self.setupBlock(
            self.parseCreateBaseVNode(node, {BVARGS.UNKNOWN1: True}, addAttributes))

    def parseCreateBlock(self, node: nodes.CallExpression,
                         addAttributes: dict[str, Any] | None = None) -> str:
        assert len(node.arguments) <= 5
        return self.setupBlock(
            self.parseCreateBaseVNode(node, {BVARGS.SHAPE_FLAG: True}, addAttributes))

    def parseRenderList(self, node: nodes.CallExpression,
                        addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: list, render method, ?, ?
        # assert 2 <= len(node.arguments) <= 4
        assert len(node.arguments) == 2
        # TODO More arguments possible

        srcIterable = nodes.getAstNode(self.ast, node.arguments[0]).toString(self.ast, self.offset,
                                                                             False)
        renderMethod = nodes.getAstNode(self.ast, node.arguments[1])
        assert isinstance(renderMethod, nodes.ArrowFunctionExpression)

        args = nodes.getAstNodeStrings(self.ast, renderMethod.params)

        if len(args) == 1:
            argumentsStr = args[0]
        else:
            argumentsStr = "(" + ", ".join(args) + ")"

        self.ctxVForCount += 1
        VForContent = self.parseRenderMethod(renderMethod, {
            "v-for": f"{argumentsStr} in {srcIterable}"
        })
        self.ctxVForCount -= 1

        return VForContent

    def parseRenderSlot(self, node: nodes.CallExpression,
                        addAttributes: dict[str, Any] | None = None) -> str:
        assert 2 <= len(node.arguments) <= 5  # Throw away
        # assert len(node.arguments) == 2
        # TODO Maybe the additional arguments have effect?

        slotName = nodes.getAstNode(self.ast, node.arguments[1]).toString(self.ast, self.offset,
                                                                          False)

        assert addAttributes is None or len(addAttributes) == 0

        # TODO Use createVNode or something
        # TODO More arguments possible

        return f"{self.offset}<slot{f"name={self.surroundString(slotName)}" if slotName != "default" else ''} />"

    def parseToDisplayString(self, node: nodes.CallExpression,
                             addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: string
        assert len(node.arguments) == 1
        string = nodes.getAstNode(self.ast, node.arguments[0])
        stringStr = string.toString(self.ast, self.offset, False).strip()
        return f"{self.offset}{{{stringStr}}}"

    def parseWithCtx(self, node: nodes.CallExpression,
                     addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: render method, ?, ?
        assert len(node.arguments) == 1
        renderMethod = nodes.getAstNode(self.ast, node.arguments[0])
        assert isinstance(renderMethod, nodes.ArrowFunctionExpression), "Invalid withCtx argument"
        return self.parseRenderMethod(renderMethod, addAttributes)

    def parseWithDirectives(self, node: nodes.CallExpression,
                            addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: node, ?
        # TODO With directives - v-model
        assert 1 <= len(node.arguments) <= 2
        node = nodes.getAstNode(self.ast, node.arguments[0])

        if addAttributes is None:
            addAttributes = {}
        addAttributes["v-model"] = "TODO"

        return self.parseTemplate(node, addAttributes)

    def parseRenderMethod(self, node: nodes.ArrowFunctionExpression,
                          addAttributes: dict[str, Any] | None = None) -> str:
        body = nodes.getAstNode(self.ast, node.body)
        if isinstance(body, nodes.BlockStatement):
            # () => {
            #   return ...
            # }
            assert isinstance(body, nodes.BlockStatement)
            assert len(body.body) == 1
            returnStatement = nodes.getAstNode(self.ast, body.body[0])
            assert isinstance(body, nodes.ReturnStatement)
            returnThing = nodes.getAstNode(self.ast, returnStatement.data)
        else:
            # () => [...]
            # () => (openBlock(), ...)
            # Or anything else
            returnThing = body

        renderedString = self.parseTemplate(returnThing, addAttributes)
        return renderedString

    # Template parser
    def parseTemplate(self, node: nodes.Node, addAttributes: dict[str, Any] | None = None) -> str:
        """Converts a template node into its string representation."""
        if isinstance(node, nodes.SequenceExpression):
            first = self.ast.getNode(node.expressions[0])
            assert isinstance(first, nodes.CallExpression)
            assert VueDecompiler.getIdentifierName(self.ast.getNode(first.callee)) == "openBlock"
            if len(first.arguments) == 0:
                self.openBlock(False)
            else:
                # TODO Maybe it can be better
                what = self.ast.getNode(first.arguments[0])
                assert isinstance(what, nodes.StaticNode)
                self.openBlock(bool(what.toData(self.ast)))

            second = nodes.getAstNode(self.ast, node.expressions[1])
            result = self.parseTemplate(second, addAttributes=addAttributes)
            return result
        elif isinstance(node, nodes.CallExpression):
            funcName = VueDecompiler.getIdentifierName(self.ast.getNode(node.callee))
            if funcName == "createBaseVNode":
                return self.parseCreateBaseVNode(node, addAttributes=addAttributes)
            elif funcName == "createVNode":
                return self.parseCreateVNode(node, addAttributes=addAttributes)
            elif funcName == "createStaticVNode":
                return self.parseCreateStaticVNode(node, addAttributes=addAttributes)
            elif funcName == "createTextVNode":
                return self.parseCreateTextVNode(node)
            elif funcName == "createElementBlock":
                return self.parseCreateElementBlock(node, addAttributes=addAttributes)
            elif funcName == "createBlock":
                return self.parseCreateBlock(node, addAttributes=addAttributes)
            elif funcName == "renderList":
                return self.parseRenderList(node, addAttributes=addAttributes)
            elif funcName == "renderSlot":
                return self.parseRenderSlot(node, addAttributes=addAttributes)
            elif funcName == "toDisplayString":
                return self.parseToDisplayString(node, addAttributes=addAttributes)
            elif funcName == "withCtx":
                return self.parseWithCtx(node, addAttributes=addAttributes)
            elif funcName == "withDirectives":
                return self.parseWithDirectives(node, addAttributes=addAttributes)
            elif funcName == "createCommentVNode":
                return ""
            else:
                raise NotImplementedError(f"Unsupported function: {funcName}")
        elif isinstance(node, nodes.Identifier):
            # If it's a static node reference
            varName = VueDecompiler.getIdentifierName(node)
            assert varName in self.varPool
            call = self.varPool[varName]
            self.component.mapFunctions(call, False, True)
            return self.parseTemplate(call, addAttributes)
        elif isinstance(node, nodes.Literal):
            return f"{self.offset}{node.type}"
        elif isinstance(node, nodes.ConditionalExpression):
            # TODO implement v-else-if
            ifBranch = nodes.getAstNode(self.ast, node.consequent)
            elseBranch = nodes.getAstNode(self.ast, node.alternate)
            ifCheck = nodes.getAstNode(self.ast, node.test)

            ifCheckStr = ifCheck.toString(self.ast, self.offset, False)
            ifBranchStr = self.parseTemplate(ifBranch, {"v-if": ifCheckStr})
            elseBranchStr = self.parseTemplate(elseBranch, {"v-else": None})

            if ifBranchStr.strip() == "":  # ifCheck ? <comment> : elseBranch
                newTest = self.ast.addNode(nodes.UnaryExpression("!", self.ast.addNode(ifCheck)))
                newCondition = nodes.ConditionalExpression(newTest, self.ast.addNode(elseBranch),
                                                           self.ast.addNode(ifBranch))
                return self.parseTemplate(newCondition, addAttributes)

            if not elseBranchStr:
                return ifBranchStr
            return ifBranchStr + NL + elseBranchStr
        elif isinstance(node, nodes.ArrayExpression):
            contentNodes = map(lambda x: self.parseTemplate(nodes.getAstNode(self.ast, x)),
                               node.elements)
            return NL.join(contentNodes)
        raise NotImplementedError(f"Unsupported node type {node.type}")

    # The entry point
    def parse(self, renderMethod: nodes.FunctionDeclaration) -> str:
        self.usedComponentsPool.clear()
        self.varPool = self.extractVarPool()
        self.blockStack.clear()
        self.currentBlock = None
        self.offsetCount = 0
        self.ctxVForCount = 0

        body = self.ast.getNode(renderMethod.body)
        assert isinstance(body, nodes.BlockStatement)
        assert len(body.body) > 0  # resolveComponent(s) + return
        for item in body.body[:-1]:
            varDeclaration = self.ast.getNode(item)
            if not isinstance(varDeclaration, nodes.VariableDeclaration):
                continue
            self.extractUsedComponents(varDeclaration)
        returnStatement = self.ast.getNode(body.body[-1])
        assert isinstance(returnStatement, nodes.ReturnStatement)
        returnThing = self.ast.getNode(returnStatement.argument)
        assert isinstance(returnThing, nodes.Node)
        return self.parseTemplate(returnThing)
