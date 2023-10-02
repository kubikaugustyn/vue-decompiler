#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from abc import abstractmethod


class DecompilerUI:
    @abstractmethod
    def ask(self, question: str) -> str:
        raise NotImplementedError("You need to use subclass of DecompilerUI")

    @abstractmethod
    def askMultiline(self, question: str) -> str:
        raise NotImplementedError("You need to use subclass of DecompilerUI")

    @abstractmethod
    def confirm(self, question: str, default: bool = True) -> bool:
        raise NotImplementedError("You need to use subclass of DecompilerUI")


class CmdUI(DecompilerUI):
    def ask(self, question: str) -> str:
        return input(question)

    def askMultiline(self, question: str, end="") -> list[str]:
        lines = []
        while True:
            line = self.ask(question)
            if line == end:
                break
            lines.append(line)
        return lines

    def confirm(self, question: str, default: bool = True) -> bool:
        answer = input(f"{question} ({'Y' if default else 'y'}/{'n' if default else 'N'}): ").lower().strip()
        if answer == "":
            # print('y' if default else 'n')
            return default
        elif answer == "y":
            return True
        elif answer == "n":
            return False
        else:
            print(f"Invalid answer '{answer}', y/n required")
            return self.confirm(question, default)
