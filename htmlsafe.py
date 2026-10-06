"""Telegram-safe HTML pagination; links/entities are never cut or omitted."""
import html
import re

TOKEN = re.compile(r'<a\b[^>]*>.*?</a>|<tg-emoji\b[^>]*>.*?</tg-emoji>|<[^>]+>|&(?:#\d+|#x[\da-fA-F]+|\w+);|[^<&]+|[<&]', re.S)
TAG = re.compile(r'^<(/?)([\w-]+)\b[^>]*>$')
ALLOWED = {'b','strong','i','em','u','ins','s','strike','del','code','pre','a','tg-emoji','tg-spoiler','span','blockquote'}


def units(s):
    return len(s.encode('utf-16-le')) // 2


def split_html(text, limit=3500):
    if limit < 128:
        raise ValueError('limit too small for safe HTML')
    text = str(text or '')
    parts, stack, buf = [], [], ''
    entities = 0

    def closing():
        return ''.join(f'</{n}>' for n, _ in reversed(stack))

    def flush():
        nonlocal buf, entities
        if buf and html.unescape(re.sub(r'<[^>]*>', '', buf)):
            parts.append(buf + closing())
        buf = ''.join(t for _, t in stack)
        entities = 0

    def add(token, atom=False):
        nonlocal buf, entities
        if units(buf + token + closing()) > limit or (atom and entities >= 70):
            flush()
        if units(buf + token + closing()) > limit:
            # Only oversized text nodes, never normal mention links, reach here.
            if atom:
                plain = html.unescape(re.sub(r'<[^>]*>', '', token))
                for ch in plain:
                    add(html.escape(ch))
                return
            for ch in token:
                if units(buf + ch + closing()) > limit:
                    flush()
                buf += ch
            return
        buf += token
        if atom:
            entities += 1

    for token in TOKEN.findall(text):
        if token.startswith('<a ') or token.startswith('<tg-emoji '):
            add(token, atom=True)
            continue
        m = TAG.match(token)
        if m and m.group(2) in ALLOWED:
            is_close, name = bool(m.group(1)), m.group(2)
            if is_close:
                if stack and stack[-1][0] == name:
                    stack.pop()
                    add(f'</{name}>')
                continue
            # Account for the future closing tag before adding the opening tag.
            if units(buf + token + closing() + f'</{name}>') > limit:
                flush()
            stack.append((name, token))
            buf += token
            continue
        if token.startswith('<'):
            token = html.escape(token)
        if token.startswith('&') and token.endswith(';'):
            add(token, atom=True)
        else:
            for node in re.findall(r'\s+|\S+', token):
                add(node)
    if buf and html.unescape(re.sub(r'<[^>]*>', '', buf)):
        parts.append(buf + closing())
    return parts or ['—']


def plain_text(text):
    return html.unescape(re.sub(r'<[^>]*>','',str(text or '')))


utf16_len=units
