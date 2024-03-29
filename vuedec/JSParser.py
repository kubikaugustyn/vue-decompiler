#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import os
import re
import zlib

from kutil.language.AST import AST
from kutil.language.languages.javascript import parseModule, nodes, Module
from kutil.language.languages.javascript.JSOptions import JSOptions
from kutil.language.languages.javascript.syntax import JSNode, JSToken
from kutil.language.languages.javascript.JSLexer import RawToken

from vuedec.types import TComponent
from vuedec.DecompilerUI import DecompilerUI
from vuedec.Cache import Cache  # In future from kutil.storage.Cache import Cache
from vuedec.Files import Files
import jsbeautifier

import kutil.language.languages.javascript.JSParser


class JSParser:
    files: Files
    file_name: str
    ui: DecompilerUI
    cache: Cache
    ast: AST | None
    entryPoint: Module | None

    componentMap: dict[str, tuple[TComponent, nodes.VariableDeclarator, str]]

    def __init__(self, files: Files, file_name: str, ui: DecompilerUI, cache_path: str,
                 immediately_parse=True):
        self.files = files
        self.file_name = file_name
        self.ui = ui
        self.cache = Cache("js-parser", cache_path)
        self.ast = None
        self.entryPoint = None

        self.componentMap = {}

        if immediately_parse:
            self.parse()

    def __crc32(self):
        with open(os.path.join(self.files.path, self.file_name), 'rb') as f:
            hash = 0
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                hash = zlib.crc32(chunk, hash)
            return "%08X" % (hash & 0xFFFFFFFF)

    def __getLines(self, lines, fromLine, toLine):
        if fromLine == toLine:
            # print(len(lines), fromLine)
            return [lines[fromLine - 1]]
        return lines[fromLine - 1:toLine]

    def __beautify(self) -> str:
        if self.cache.hasFile(f"beautified-{self.file_name}"):
            content = self.cache.getFile(f"beautified-{self.file_name}")
        else:
            content = self.files.get(self.file_name)
            print(f"Applying beautifier to {self.file_name}", end="")
            content = jsbeautifier.beautify(content)
            content = content.replace("\r\n", "\n")
            self.cache.setFile(f"beautified-{self.file_name}", content)
            print(" - DONE")

        return content

    def parse(self) -> tuple[AST, nodes.Module]:
        if self.ast is not None and self.entryPoint is not None:
            return self.ast, self.entryPoint

        hash = self.__crc32()  # Cache beautifying
        if hash != self.cache.get(f"hash-{self.file_name}"):
            beautified_file = self.__beautify()
            self.cache.set(f"hash-{self.file_name}", hash)
        else:
            beautified_file = self.cache.getFile(f"beautified-{self.file_name}")
        options: JSOptions = JSOptions()
        print(f"Parsing {self.file_name}", end="")
        self.ast, self.entryPoint = parseModule(beautified_file, options)
        print(" - DONE")
        return self.ast, self.entryPoint

    def registerComponent(self, component: TComponent, name: str, varName: str,
                          varNode: nodes.VariableDeclarator):
        self.componentMap[name] = (component, varNode, varName)

    def unregisterComponent(self, name: str):
        del self.componentMap[name]

    def findComponentNameByVarName(self, varName: str, otherVarName: str | None = None) -> str:
        for key, (_, _, cmpVarName) in self.componentMap.items():
            if cmpVarName == varName:
                return key
            if otherVarName is not None and otherVarName == cmpVarName:
                return key
        raise KeyError("Component var name not found")

    def findComponentNameByImport(self, importedName: str, usedName: str) -> tuple[str, str]:
        from vuedec.VueDecompiler import VueDecompiler

        for node in self.ast.getNodes(self.entryPoint.body):
            if node.type is not JSNode.ImportDeclaration:
                continue
            assert isinstance(node, nodes.ImportDeclaration)

            sourceNode = self.ast.getNode(node.source)
            assert isinstance(sourceNode, nodes.Literal)

            # source = VueDecompiler.absPath(str(sourceNode.value))
            # match = re.match(r"([A-Za-z]+)([\w\W]+)(.min)?(.js)?", source)
            # source = match.group(1)

            for specifier in self.ast.getNodes(node.specifiers):
                assert isinstance(specifier, nodes.ImportSpecifier)

                localNode = self.ast.getNode(specifier.local)
                assert isinstance(localNode, nodes.Identifier)

                if localNode.name != importedName and localNode.name != usedName:
                    continue

                return usedName, node.toString(self.ast)
        raise KeyError("Component var name not found")
