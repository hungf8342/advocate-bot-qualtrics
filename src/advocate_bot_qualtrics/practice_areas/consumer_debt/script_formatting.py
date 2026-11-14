"""Render approved script paragraphs and Word lists as structured, safe UI blocks."""
from __future__ import annotations

from pathlib import Path
import re

import yaml

from .rendering import script_text

with Path(__file__).with_suffix('.yaml').open(encoding='utf-8') as source:
    SOURCE_FORMATTING = yaml.safe_load(source)


def normalized(text: str) -> str:
    return ' '.join(text.split())


STATIC = {}
DYNAMIC = {}
for paragraph in SOURCE_FORMATTING['paragraphs']:
    text = paragraph['text']
    tokens = tuple(dict.fromkeys(re.findall(r'\[[^\]]+\]',text)))
    if tokens:
        first = normalized(text).split(' ',1)[0]
        DYNAMIC.setdefault('*' if first.startswith('[') else first,[]).append((paragraph,tokens))
    else:
        STATIC.setdefault(normalized(text),paragraph)


STATIC_PREFIXES = {}
for key, paragraph in STATIC.items():
    if len(key)>=20 or 'list_level' in paragraph:
        STATIC_PREFIXES.setdefault(key.split(' ',1)[0],[]).append((key,paragraph))


class ScriptFormatter:
    def __init__(self, session):
        self.session = session
        self.tokens = {}
        self.dynamic = {}

    def dynamic_entries(self, first):
        if first not in self.dynamic:
            entries=[]
            for paragraph,tokens in [*DYNAMIC.get(first,[]),*DYNAMIC.get('*',[])]:
                rendered=paragraph['text']
                for token in tokens:
                    if token not in self.tokens:
                        self.tokens[token]=script_text(token,self.session)
                    rendered=rendered.replace(token,self.tokens[token])
                entries.append((normalized(rendered),{**paragraph,'text':rendered}))
            self.dynamic[first]=entries
        return self.dynamic[first]

    def match(self, text):
        key = normalized(text)
        if key in STATIC:
            return STATIC[key]
        first = key.split(' ',1)[0]
        return next((paragraph for candidate,paragraph in self.dynamic_entries(first) if candidate==key),None)

    def paragraphs(self, text):
        whole=self.match(text)
        if whole:
            return [whole]
        result=[]
        for line in text.splitlines():
            if not line.strip():
                continue
            remaining=normalized(line)
            matched=False
            while remaining:
                first=remaining.split(' ',1)[0]
                candidates=[*STATIC_PREFIXES.get(first,[]),*self.dynamic_entries(first)]
                valid=[(key,p) for key,p in candidates if remaining.startswith(key)
                       and (len(key)==len(remaining) or remaining[len(key)].isspace())]
                if not valid:
                    result.append({'text':remaining if matched else line.strip()})
                    break
                key,paragraph=max(valid,key=lambda item:len(item[0]))
                result.append(paragraph)
                matched=True
                remaining=remaining[len(key):].lstrip()
        return result

    def blocks(self, texts: list[str]) -> list[dict]:
        blocks=[]
        list_stack=[]
        base_level=0
        for text in texts:
            if not text.strip():
                continue
            # A source paragraph may itself contain a deliberate hard line break.
            for paragraph in self.paragraphs(text):
                if 'list_level' not in paragraph or paragraph.get('quote_container'):
                    blocks.append({'type':'paragraph','text':paragraph['text']})
                    list_stack=[]
                    continue
                level=paragraph['list_level']
                ordered=paragraph.get('list_format')!='bullet'
                if not list_stack:
                    base_level=level
                    block={'type':'list','ordered':ordered,'items':[]}
                    blocks.append(block)
                    list_stack=[block]
                depth=max(0,level-base_level)
                while len(list_stack)>depth+1:
                    list_stack.pop()
                if depth>=len(list_stack) and list_stack[-1]['items']:
                    nested={'type':'list','ordered':ordered,'items':[]}
                    list_stack[-1]['items'][-1].setdefault('children',[]).append(nested)
                    list_stack.append(nested)
                list_stack[-1]['items'].append({'text':paragraph['text']})
        return blocks
