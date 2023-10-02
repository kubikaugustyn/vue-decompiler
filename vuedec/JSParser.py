#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import os
import zlib

from esprima import parseScript
from esprima.tokenizer import Tokenizer, BufferEntry
from esprima.token import *
from esprima.nodes import *
from vuedec.DecompilerUI import DecompilerUI
from vuedec.Cache import Cache
from vuedec.Files import Files
import jsbeautifier


class JSParser:
    files: Files
    file_name: str
    ui: DecompilerUI
    cache: Cache

    def __init__(self, files: Files, file_name: str, ui: DecompilerUI, cache_path: str, immediately_parse=True):
        self.files = files
        self.file_name = file_name
        self.ui = ui
        self.cache = Cache("js-parser", cache_path)
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

    def __beautifyAndPatch(self):
        if self.cache.hasFile(f"beautified-{self.file_name}"):
            content = self.cache.getFile(f"beautified-{self.file_name}")
        else:
            content = self.files.get(self.file_name)
            print(f"Applying beautifier to {self.file_name}", end="")
            content = jsbeautifier.beautify(content)
            content = content.replace("\r\n", "\n")
            self.cache.setFile(f"beautified-{self.file_name}", content)
            print(" - DONE")
        if self.cache.hasFile(f"patched-{self.file_name}"):
            patched_file = self.cache.getFile(f"patched-{self.file_name}")
        else:
            # Because both JS parsing modules don't know ES6 ?? operator, I have to find a workaround
            # They also don't know ES?, probably ES6 try...catch {} instead of catch (e) {}, I have to find a workaround
            # AHHHHHHHHHHHHHHHH
            # It doesn't even know optional chaining (?.) operator :-/
            # How am I supposed to use the library then ?!
            tokenizer = Tokenizer(content, {"loc": True, "range": True, "comment": False, "tolerant": False})
            new_lines = content.splitlines(False)
            changes = []
            catch_clause_lines = []
            catch_line = 0
            prev = None
            while True:
                token: BufferEntry = tokenizer.getNextToken()
                if not token:
                    break
                if token.type == TokenName.get(Token.Keyword):
                    prev = None
                    if token.value == "catch":
                        catch_line = token.loc.start.line
                elif token.type == TokenName.get(Token.Punctuator):
                    if token.value == "?":
                        catch_line = 0
                        if prev:
                            l1 = prev.loc.start.line
                            l2 = token.loc.end.line
                            oneLine = l1 == l2
                            changes.append((l1, l2, oneLine))
                            prev = None
                        else:
                            prev = token
                    else:
                        prev = None
                    if token.value == "{" and catch_line:
                        catch_clause_lines.append(catch_line)
                        catch_line = 0
                    elif token.value == "(" and catch_line:
                        # Everything is right
                        catch_line = 0
                else:
                    prev = None
            if len(changes):
                print(f"We've found {len(changes)} nullish coalescing operators in your JS file. "
                      f"We have to replace them before we can continue.")
                use_cache = self.ui.confirm("Use cached changes", True)
                for l1, l2, oneLine in changes:
                    cached = self.cache.get(f"{self.file_name}-{l1}-{l2}")
                    if not cached:
                        print(f"\nCheck the following JavaScript code snippet ({self.file_name}, lines {l1} to {l2}):")
                        print("\n", "\n".join(self.__getLines(new_lines, l1, l2)))
                        print("\nand submit patched code.")
                    patched = False
                    if cached:
                        cached_lines: list[str] = cached.splitlines(False)
                        if not use_cache:
                            size = max(map(lambda line: len(line), self.__getLines(new_lines, l1, l2))) + 5
                            cached_size = max(map(lambda l: len(l), cached_lines)) + 5
                            print(f"\nCheck the following patch:\n")
                            for i in range(l1 - 1, l2):
                                print(new_lines[i].ljust(size, " "), end="")
                                if i - l1 < len(cached_lines):
                                    print("-->", cached_lines[i - l1 + 1].rjust(cached_size, " "))
                            print()
                        if use_cache or self.ui.confirm("Accept this patch?"):
                            for i in range(l1 - 1, l2):
                                if i - l1 < len(cached_lines):
                                    new_lines[i] = cached_lines[i - l1 + 1]
                            patched = True
                    if not patched:
                        patch_lines = self.ui.askMultiline("Enter line (blank to end): ")
                        for i in range(l1, l2):
                            if i - l1 < len(patch_lines):
                                new_lines[i] = patch_lines[i - l1]
                        self.cache.set(f"{self.file_name}-{l1}-{l2}", "\n".join(patch_lines))
            print(catch_clause_lines)
            if len(catch_clause_lines):
                check = not self.ui.confirm("Automatically replace bad try...catch clauses?", False)
                for l in catch_clause_lines:
                    l -= 1
                    new_line: str = new_lines[l].replace("catch {", "catch (_patch_error_) {")
                    if check:
                        print(f"Check the following patch:\n\n{new_lines[l]}     -->     {new_line}\n")
                        if not self.ui.confirm("Accept this patch?"):
                            new_line = self.ui.ask("Enter the right patch: ")
                    new_lines[l] = new_line
            patched_file = "\n".join(new_lines)
            self.cache.setFile(f"patched-{self.file_name}", patched_file)
        return patched_file

    def parse(self):
        hash = self.__crc32()  # Cache beautifing and patching
        if hash != self.cache.get(f"hash-{self.file_name}") or not self.cache.hasFile(f"patched-{self.file_name}"):
            patched_file = self.__beautifyAndPatch()
            self.cache.set(f"hash-{self.file_name}", hash)
        else:
            patched_file = self.cache.getFile(f"patched-{self.file_name}")
        ast: Script = parseScript(patched_file)
        pass
