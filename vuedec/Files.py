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

    def setRaw(self, file_name: str, data: bytes):
        self.__cache[file_name] = data
        path = os.path.join(self.path, file_name)
        with open(path, "wb+") as f:
            f.write(data)

    def set(self, file_name: str, data: str):
        self.setRaw(file_name, data.encode("utf-8"))


if __name__ == '__main__':
    files = Files("")
    print(files.get("Files.py"))
