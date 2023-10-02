#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import os.path


class Files:
    path: str
    __cache: dict[str, bytes]

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.__cache = {}

    def has(self, file_name: str) -> bool:
        return os.path.exists(os.path.join(self.path, file_name))

    def getRaw(self, file_name: str) -> bytes:
        if file_name in self.__cache:
            return self.__cache.get(file_name)
        if not self.has(file_name):
            raise AttributeError("404 File not found")
        path = os.path.join(self.path, file_name)
        with open(path, "rb+") as f:
            file = f.read()
        self.__cache[file_name] = file
        return file

    def get(self, file_name: str) -> str:
        return self.getRaw(file_name).decode("utf-8")


if __name__ == '__main__':
    f = Files("")
    print(f.get("Files.py"))
