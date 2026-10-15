"""Tiny S-expression reader/writer for KiCad files (enough for symbol libraries and schematics).
From ~/wifi-game-boy-cartridge/hw/rev-b/tools/sexp.py; changed to keep strings raw so files round-trip exactly."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


def parse(text):
    stack, cur = [], []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == '':
                break
            raise ValueError(f'bad token at {pos}: {text[pos:pos+40]!r}')
        pos = m.end()
        op, cl, st, at = m.groups()
        if op:
            stack.append(cur)
            cur = []
        elif cl:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif st is not None:
            cur.append(Str(st[1:-1]))   # kept raw: escapes such as \\n stay as written (KiCad 10 rejects real newlines)
        else:
            cur.append(at)
    return cur[0] if len(cur) == 1 else cur


class Str(str):
    """A quoted string (keeps quoting on output)."""


def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return '()'
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return '(' + ' '.join(dump(x) for x in node) + ')'
        pad = '\t' * (indent + 1)
        parts = [dump(node[0])]
        out = '(' + parts[0]
        for x in node[1:]:
            if isinstance(x, list):
                out += '\n' + pad + dump(x, indent + 1)
            else:
                out += ' ' + dump(x)
        return out + '\n' + '\t' * indent + ')'
    if isinstance(node, Str):
        return '"' + node + '"'      # raw (see parse); new strings must not contain quotes or backslashes
    return str(node)


def find(node, key):
    """All direct children lists whose head is key."""
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


def walk(node):
    if isinstance(node, list):
        yield node
        for c in node:
            yield from walk(c)
