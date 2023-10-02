#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from vuedec.DecompilerUI import DecompilerUI, CmdUI
from vuedec.Files import Files
from vuedec.JSParser import JSParser


class VueDecompiler:
    source: str
    target: str
    cache: str
    ui: DecompilerUI

    def __init__(self, source: str, target: str, cache: str):
        self.source = source
        self.target = target
        self.cache = cache
        self.ui = CmdUI()

    def set_ui(self, new_ui):
        if not isinstance(new_ui, DecompilerUI):
            raise AttributeError("Bad UI class")
        self.ui = new_ui

    def decompile(self):
        f = Files(self.source)
        u = self.ui
        main_file_name = "index.js" if f.has("index.js") else u.ask("Enter main file name: ")
        i = JSParser(f, main_file_name, u, self.cache)
