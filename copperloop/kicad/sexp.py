"""Minimal KiCad s-expression parser/serializer."""

class Sym(str):
    """Bare symbol token (unquoted)."""
    pass

def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            i += 1
        elif c == '(':
            yield '('; i += 1
        elif c == ')':
            yield ')'; i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == '\\' and j + 1 < n:
                    buf.append(text[j]); buf.append(text[j+1]); j += 2
                elif text[j] == '"':
                    break
                else:
                    buf.append(text[j]); j += 1
            yield ('STR', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            yield ('SYM', text[i:j])
            i = j

def parse(text):
    stack = [[]]
    for tok in tokenize(text):
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            kind, val = tok
            if kind == 'STR':
                stack[-1].append(('str', val))
            else:
                stack[-1].append(Sym(val))
    return stack[0]

def is_list(x):
    return isinstance(x, list)

def tag(x):
    return x[0] if is_list(x) and x and isinstance(x[0], Sym) else None

def atom(x):
    """Return python value of an atom node."""
    if isinstance(x, tuple) and x[0] == 'str':
        return x[1]
    return str(x)

def find_all(node, name):
    return [c for c in node if is_list(c) and tag(c) == name]

def find(node, name):
    for c in node:
        if is_list(c) and tag(c) == name:
            return c
    return None

def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

def serialize(node, indent=0):
    """Serialize a parsed node back to text (KiCad-ish formatting)."""
    if isinstance(node, tuple) and node[0] == 'str':
        return '"%s"' % esc(node[1])
    if isinstance(node, Sym):
        return str(node)
    # list
    parts = [serialize(c) for c in node]
    return '(' + ' '.join(parts) + ')'
