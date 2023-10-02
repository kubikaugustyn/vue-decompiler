#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import os.path
import shutil
import sys
from vuedec import *


def main():
    if len(sys.argv) != 4:
        print("Usage: ")
        sys.exit(1)
    source = sys.argv[1]
    target = sys.argv[2]
    cache = sys.argv[3]
    if not os.path.exists(source):
        print("Source path must exist")
        sys.exit(1)
    if not os.path.isdir(source):
        print("Source path must be directory XD")
        sys.exit(1)
    if os.path.exists(target):
        shutil.rmtree(target)
    os.mkdir(target)
    if not os.path.exists(cache):
        os.mkdir(cache)

    vd = VueDecompiler(source, target, cache)
    # vd.set_ui(CmdUI()) - default
    vd.decompile()


if __name__ == '__main__':
    main()
