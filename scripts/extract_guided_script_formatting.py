#!/usr/bin/env python3
"""Extract paragraph/list structure from the approved Word source without flattening it."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/source-material/2026-11-07/2026.11.07 Affirmative-Defense-Scripts.docx'
OUTPUT = ROOT / 'src/advocate_bot_qualtrics/practice_areas/consumer_debt/guided_script_formatting.yaml'
NS = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{'+NS['w']+'}'


def extract_formatting(source: Path) -> dict:
    with ZipFile(source) as document:
        root = ET.fromstring(document.read('word/document.xml'))
        numbering = ET.fromstring(document.read('word/numbering.xml'))
    abstract = {node.get(W+'abstractNumId'): {
        level.get(W+'ilvl'):level.find('w:numFmt',NS).get(W+'val')
        for level in node.findall('w:lvl',NS)} for node in numbering.findall('w:abstractNum',NS)}
    numbers = {node.get(W+'numId'):node.find('w:abstractNumId',NS).get(W+'val')
               for node in numbering.findall('w:num',NS)}
    paragraphs = []
    quoted = False
    for paragraph in root.findall('.//w:p',NS):
        text = ''.join(node.text or '' if node.tag==W+'t' else '\n' if node.tag==W+'br' else '\t'
                       for node in paragraph.iter() if node.tag in {W+'t',W+'br',W+'tab'})
        style = paragraph.find('w:pPr/w:pStyle',NS)
        runs = [run for run in paragraph.findall('.//w:r',NS) if ''.join(run.itertext()).strip()]
        bold = bool(runs) and all(run.find('w:rPr/w:b',NS) is not None and
                run.find('w:rPr/w:b',NS).get(W+'val') not in {'0','false'} for run in runs)
        if bold or (style is not None and style.get(W+'val','').startswith('Heading')):
            quoted = False
        text = text.strip()
        quote_container = text.startswith('“') and text.endswith('”')
        if text.startswith('“'):
            quoted = True
            text = text[1:]
        if quoted and text.endswith('”'):
            text = text[:-1]
            quoted = False
        if not text.strip():
            continue
        entry = {'text':text.strip()}
        num = paragraph.find('w:pPr/w:numPr',NS)
        if num is not None:
            level = num.find('w:ilvl',NS).get(W+'val','0')
            number = num.find('w:numId',NS).get(W+'val')
            entry.update(list_level=int(level), list_format=abstract[numbers[number]][level])
            if quote_container:
                entry['quote_container'] = True
        paragraphs.append(entry)
    return {'source':str(source.relative_to(ROOT)), 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'paragraphs':paragraphs}


def serialize(data):
    return '# Generated from the November 7 Word document; preserve paragraph and list metadata.\n'+yaml.safe_dump(data,sort_keys=False,allow_unicode=True,width=100)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    content=serialize(extract_formatting(SOURCE))
    if args.check:
        if OUTPUT.read_text(encoding='utf-8') != content:
            raise SystemExit('Guided formatting differs from the approved November 7 source. Regenerate it.')
    else:
        OUTPUT.write_text(content,encoding='utf-8')


if __name__=='__main__':
    main()
