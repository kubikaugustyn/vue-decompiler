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
from vuedec.Component import Component, _VUE_RENDER_ARGUMENTS
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

BASE_VUE_COMPONENTS: dict[str, str] = {"Fragment": "template", "Transition": "Transition"}
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

    def __init__(self, component: Component):
        self.component = component
        self.ast = component.ast
        self.sourceFile = component.sourceFile

        self.usedComponentsPool = {}
        self.varPool = {}
        self.blockStack = []
        self.currentBlock = None
        self.offsetCount = 0

    # Helper methods
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
                    assert initI is not None

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

    def parseNormalizeStyle(self, node: nodes.CallExpression) -> str:
        return '"NORMALIZE STYLE"'

    def parseMethodHandler(self, node: nodes.BinaryExpression) -> str | None:
        # _cache[0] || _cache[0] = <method>

        second = self.ast.getNode(node.right)
        if not isinstance(second, nodes.AssignmentExpression) or second.operator != "=":
            return None
        method = nodes.getAstNode(self.ast, second.right)

        return method.toString(self.ast, self.offset, False)

    def parseAttributeCall(self, node: nodes.Node) -> str | None:
        if isinstance(node, nodes.CallExpression):
            name = VueDecompiler.getIdentifierName(self.ast.getNode(node.callee))
            if name == "normalizeClass":
                # TODO What is the difference between normalizeClass and normalizeStyle?
                return self.parseNormalizeStyle(node)
        elif isinstance(node, nodes.BinaryExpression):
            if node.operator == "||":
                return self.parseMethodHandler(node)
        return None

    def parseSlots(self, node: nodes.ObjectExpression) -> str | None:
        # TODO Deal better with only the default slot
        # TODO Fix the offsets
        # <template v-slot:default /> - nope
        # <template #slotId /> - yes
        slots: list[str] = []

        oldOffset = self.offsetCount
        self.offsetCount = 0

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

            slots.append(self.parseTemplate(value, {f"#{slotName}": None}))

        if len(slots) == 0:
            raise ValueError("There must be at least 1 slot")

        self.offsetCount = oldOffset

        slots = list(map(lambda slot: self.offsetStringBy(slot, self.offset), slots))

        return "".join(slots)

    @staticmethod
    def offsetStringBy(string: str, off: str) -> str:
        return NL.join(map(lambda line: off + line, string.split(NL)))

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
            if value is None:
                attributeList.append(paramName)
                continue

            if isinstance(value, nodes.Node):
                if isinstance(value, nodes.StaticNode):
                    valueStr = value.toDataStr(self.ast)
                else:
                    valueStr = value.toString(self.ast, self.offset, False)
            else:
                valueStr = value
            if valueStr.startswith('"') and valueStr.endswith('"'):
                attributeList.append(f"{paramName}={valueStr}")
            else:
                attributeList.append(f'{paramName}="{valueStr}"')

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
            newPropsDict = {}
            for key, value in props.items(self.ast):
                if isinstance(key, nodes.StaticNode):
                    keyStr = key.toDataOrString(self.ast)
                else:
                    keyStr = key.toString(self.ast)
                # TODO Add all values
                # TODO For some reason :onClick appears inside renderList
                isAsString = value.type in {JSNode.Literal} or keyStr in {"onClick"}

                valStr = self.parseAttributeCall(value)
                if valStr is None:
                    if isinstance(value, nodes.StaticNode):
                        valStr = str(value.toDataOrString(self.ast)).strip()
                    else:
                        valStr = value.toString(self.ast)

                # TODO Fix attributes being not properly 'escaped'
                if valStr.startswith('"') and valStr.endswith('"'):
                    newPropsDict[keyStr] = valStr
                else:
                    newPropsDict[("" if isAsString else ":") + keyStr] = '"' + valStr + '"'
            props = newPropsDict

            for key, value in props.items():
                isDynamic = dynProps is not None and key in dynProps
                attributeList.append(f"{':' if isDynamic else ''}{key}={value}")

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
                string = str(childrenList.toData(self.ast)).strip()
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
                    children = off + TABULATOR + string
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
                         addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: type, props, children, patchFlag, dynamicProps, unknown1
        # return createBaseVNode(type, props, children, patchFlag, dynamicProps, <not an argument>,
        #   unknown1, true)
        params = self.getParamsFromFnCall(node, V_NODE_ARGS,
                                          None,
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

        srcIterable = nodes.getAstNode(self.ast, node.arguments[0]).toString(self.ast)
        renderMethod = nodes.getAstNode(self.ast, node.arguments[1])
        assert isinstance(renderMethod, nodes.ArrowFunctionExpression)

        argumentsStr = ", ".join(nodes.getAstNodeStrings(self.ast, renderMethod.params))

        return self.parseRenderMethod(renderMethod, {
            "v-for": f"{argumentsStr} in {srcIterable}"
        })

    def parseToDisplayString(self, node: nodes.CallExpression,
                             addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: string
        assert len(node.arguments) == 1
        string = nodes.getAstNode(self.ast, node.arguments[0])
        stringStr = string.toString(self.ast).strip()
        return f"{self.offset}{{{stringStr}}}"

    def parseWithCtx(self, node: nodes.CallExpression,
                     addAttributes: dict[str, Any] | None = None) -> str:
        # Params as following: render method, ?, ?
        assert len(node.arguments) == 1
        renderMethod = nodes.getAstNode(self.ast, node.arguments[0])
        assert isinstance(renderMethod, nodes.ArrowFunctionExpression), "Invalid withCtx argument"
        return self.parseRenderMethod(renderMethod, addAttributes)

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
            elif funcName == "createElementBlock":
                return self.parseCreateElementBlock(node, addAttributes=addAttributes)
            elif funcName == "createBlock":
                return self.parseCreateBlock(node, addAttributes=addAttributes)
            elif funcName == "renderList":
                return self.parseRenderList(node, addAttributes=addAttributes)
            elif funcName == "toDisplayString":
                return self.parseToDisplayString(node, addAttributes=addAttributes)
            elif funcName == "withCtx":
                return self.parseWithCtx(node, addAttributes=addAttributes)
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
