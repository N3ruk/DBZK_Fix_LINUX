"""Small position-preserving editor for Steam's text KeyValues files.

Unlike a deserialize/serialize roundtrip, only the requested value or missing
branch is edited. Unknown syntax and duplicate targeted keys are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re


class VDFError(ValueError):
    pass


@dataclass
class Token:
    value: str
    start: int
    end: int
    kind: str = "word"


@dataclass
class Node:
    key: Token | None
    value: Token | None = None
    children: list = field(default_factory=list)
    closing: int = 0

    def child(self, key):
        found = [n for n in self.children if n.key.value.casefold() == key.casefold()]
        if len(found) > 1:
            raise VDFError("Clave VDF ambigua: " + key)
        return found[0] if found else None


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t') + '"'


def tokenize(text):
    pos = 0
    while pos < len(text):
        if text[pos].isspace() or (pos == 0 and text[pos] == '\ufeff'):
            pos += 1
            continue
        if text.startswith('//', pos):
            end = text.find('\n', pos)
            pos = end if end >= 0 else len(text)
            continue
        if text.startswith('/*', pos):
            end = text.find('*/', pos + 2)
            if end < 0:
                raise VDFError("Comentario VDF sin cerrar")
            pos = end + 2
            continue
        start = pos
        ch = text[pos]
        if ch in '{}':
            pos += 1
            yield Token(ch, start, pos, ch)
        elif ch == '"':
            pos += 1
            value = ''
            while pos < len(text) and text[pos] != '"':
                if text[pos] == '\\' and pos + 1 < len(text):
                    nxt = text[pos + 1]
                    value += {'n': '\n', 'r': '\r', 't': '\t', '"': '"', '\\': '\\'}.get(nxt, '\\' + nxt)
                    pos += 2
                else:
                    value += text[pos]
                    pos += 1
            if pos == len(text):
                raise VDFError("Cadena VDF sin cerrar")
            pos += 1
            yield Token(value, start, pos)
        else:
            while pos < len(text) and not text[pos].isspace() and text[pos] not in '{}"':
                pos += 1
            if pos == start:
                raise VDFError("Sintaxis VDF no reconocida")
            value = text[start:pos]
            if value.startswith('['):
                raise VDFError("Condicional VDF no compatible; no se ha modificado")
            yield Token(value, start, pos)


class Document:
    def __init__(self, text):
        self.text = text
        self.newline = '\r\n' if '\r\n' in text else '\n'
        tokens = list(tokenize(text))
        index = 0

        def parse(nested=False):
            nonlocal index
            node = Node(None, closing=len(text))
            while index < len(tokens):
                key = tokens[index]
                index += 1
                if key.kind == '}':
                    if not nested:
                        raise VDFError("Llave VDF inesperada")
                    node.closing = key.start
                    return node
                if key.kind != 'word' or index >= len(tokens):
                    raise VDFError("Par clave/valor VDF incompleto")
                value = tokens[index]
                index += 1
                if value.kind == '{':
                    child = parse(True)
                    child.key = key
                elif value.kind == 'word':
                    child = Node(key, value)
                else:
                    raise VDFError("Valor VDF inesperado")
                node.children.append(child)
            if nested:
                raise VDFError("Objeto VDF sin cerrar")
            return node

        self.root = parse()

    def find(self, path):
        node = self.root
        for key in path:
            if node.value is not None:
                raise VDFError("Se esperaba una sección VDF: " + key)
            node = node.child(key)
            if node is None:
                return None
        return node

    def get(self, path, default=None):
        node = self.find(path)
        if node is None:
            return default
        if node.value is None:
            raise VDFError("Se esperaba una cadena VDF")
        return node.value.value

    def set(self, path, value):
        node = self.find(path)
        if node is not None:
            if node.value is None:
                raise VDFError("Se esperaba una cadena VDF")
            return self.text[:node.value.start] + quote(value) + self.text[node.value.end:]
        parent = self.root
        depth = 0
        for key in path[:-1]:
            child = parent.child(key)
            if child is None:
                break
            if child.value is not None:
                raise VDFError("No se puede insertar en una cadena VDF")
            parent = child
            depth += 1
        lines = []
        for offset, key in enumerate(path[depth:-1]):
            indent = '\t' * (depth + offset)
            lines.extend([indent + quote(key), indent + '{'])
        lines.append('\t' * (len(path) - 1) + quote(path[-1]) + '\t\t' + quote(value))
        for level in range(len(path) - 2, depth - 1, -1):
            lines.append('\t' * level + '}')
        insert = self.newline.join(lines) + self.newline
        pos = parent.closing
        line_start = self.text.rfind('\n', 0, pos) + 1
        if not self.text[line_start:pos].strip():
            pos = line_start
        elif pos and self.text[pos - 1] not in '\r\n':
            insert = self.newline + insert
        return self.text[:pos] + insert + self.text[pos:]

    def delete(self, path):
        node = self.find(path)
        if node is None:
            return self.text
        if node.value is None:
            raise VDFError("Solo se pueden eliminar valores, no secciones")
        return self.text[:node.key.start] + self.text[node.value.end:]


APP_PATH = ['UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps', '851850', 'LaunchOptions']
