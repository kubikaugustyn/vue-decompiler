#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

import json
import os.path


class Cache:
    name: str
    path: str
    data: dict

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.load()

    def __open(self, mode):
        path = os.path.join(self.path, self.name + ".json")
        # print(path, mode, os.path.exists(path))
        if not os.path.exists(path):
            with open(path, "w+") as f:
                f.write("{}")
        return open(path, mode)

    def load(self):
        self.data = json.load(self.__open("r+"))
        return self.data

    def save(self):
        json.dump(self.data, self.__open("w+"))
        return self.data

    def get(self, key: str, default=None, reload=False):
        if reload:
            self.load()
        return self.data.get(key, default)

    def set(self, key: str, value, save=True):
        self.data[key] = value
        if save:
            self.save()

    def __getFilePath(self, key):
        return os.path.join(self.path, f"{self.name}-{key}")

    def getFileRaw(self, filename: str, default=None, reload=False) -> bytes:
        if reload:
            self.load()
        path = self.data.get(filename)
        if not path:
            path = self.__getFilePath(filename)
        if not os.path.exists(path):
            return default
        with open(path, "rb") as f:
            return f.read()

    def getFile(self, filename: str, default=None, reload=False) -> str:
        raw = self.getFileRaw(filename, default, reload)
        if not raw:
            return default
        return raw.decode("utf-8")

    def setFileRaw(self, filename: str, value: bytes, save=True):
        path = self.__getFilePath(filename)
        self.data[filename] = path
        with open(path, "wb+") as f:
            f.write(value)
        if save:
            self.save()

    def setFile(self, filename: str, value: str, save=True):
        self.setFileRaw(filename, value.encode("utf-8"), save)

    def has(self, key, reload=False):
        if reload:
            self.load()
        return key in self.data

    def hasFile(self, filename, reload=False):
        has_path = self.has(filename, reload)
        if has_path:
            path = self.data.get(filename)
        else:
            path = self.__getFilePath(filename)
        return os.path.exists(path)


if __name__ == '__main__':
    c = Cache("test", fr"C:{os.getenv('homepath')}\Desktop\Kubik\vue-decompiler\cache")
    print("SUS" if c.get("sus") else "Not sus")
    c.set("sus", True)
