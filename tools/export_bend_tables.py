"""曲げ見積り計算書.html から単価表を取り出して、スキル用の bend_tables.json を作る。

価格の正本は 曲げ見積り計算書.html の定数（CLAUDE.md 参照）。手で書き写さず、必ずこれで写す。

  python tools/export_bend_tables.py

出力: skills/mage-koutin/scripts/bend_tables.json
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SRC = os.path.join(PROJ, '曲げ見積り計算書.html')
OUT = os.path.join(PROJ, 'skills', 'mage-koutin', 'scripts', 'bend_tables.json')

def block(src, name):
    return src.split('var ' + name)[1].split('];')[0]

def rows(body):
    return [{'shape': s, 'w': int(w), 'c': [int(x) for x in c.split(',')]}
            for s, w, c in re.findall(r"\{shape:'([^']+)',w:(\d+),\s*c:\[([^\]]+)\]\}", body)]

def obj(src, name):
    body = src.split('var ' + name)[1].split('}')[0]
    return {k.strip().strip("'\""): float(v) for k, v in re.findall(r"'?([\w.]+)'?\s*:\s*([\d.]+)", body)}

def main():
    src = open(SRC, encoding='utf-8').read()
    data = {
        '_出どころ': '曲げ見積り計算書.html（価格の正本）。tools/export_bend_tables.py で自動生成。手で編集しない。',
        'length_thresholds': [835, 1670, 2505, 3048, 99999],
        'length_labels': ['〜835mm', '〜1670mm', '〜2505mm', '〜3048mm', '3048mm超'],
        'bending_table': rows(block(src, 'BENDING_TABLE')),
        'shima_table': rows(block(src, 'SHIMA_TABLE')),
        'shima_unit_weights': obj(src, 'SHIMA_UNIT_WEIGHTS'),
        'shape_bend_count': {k: int(v) for k, v in obj(src, 'SHAPE_BEND_COUNT =').items()},
        'shima_shape_bend_count': {k: int(v) for k, v in obj(src, 'SHIMA_SHAPE_BEND_COUNT').items()},
        'komono_table': {k: int(v) for k, v in obj(src, 'KOMONO_DEFAULT_TABLE').items()},
        'komono_min': 300,
        'komono_limit': {'weight_kg': 5.0, 'length_mm': 835},
        'density': 7.85,
        'yocho': [[2.3, 50], [3.2, 30], [99, 20]],
        'qty_factor': {'thresh1': 4, 'thresh2': 19, 'factor1': 1.5, 'factor2': 1.0, 'factor3': 0.8},
        'options': {
            'nakagoshi': {'label': '中押し', 'type': 'mult', 'value': 1.5},
            'reverse':   {'label': '逆曲げ', 'type': 'mult', 'value': 1.2},
            'long':      {'label': '長尺目押し', 'type': 'add', 'value': 2500, 'min_length_mm': 1000},
            'block':     {'label': 'ブロック', 'type': 'add', 'value': 3000},
            'hazeri':    {'label': 'ハゼ折', 'type': 'add', 'value': 2000},
        },
        'komono_options': {
            'nakagoshi': {'label': '中押し', 'type': 'mult', 'value': 1.5},
            'reverse':   {'label': '逆曲げ', 'type': 'mult', 'value': 1.2},
            'hazeri':    {'label': 'ハゼ折', 'type': 'add', 'value': 2000},
        },
    }
    for key, n in [('bending_table', 56), ('shima_table', None)]:
        got = len(data[key])
        if not got or (n and got != n):
            raise SystemExit(f'{key} の行数が想定と違います（{got}行）。HTMLの書き方が変わっていないか確認すること。')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{OUT} を作りました（通常 {len(data["bending_table"])}行 / 縞板 {len(data["shima_table"])}行 / '
          f'小物 {len(data["komono_table"])}段 / 形状 {len(data["shape_bend_count"])}種）')

if __name__ == '__main__':
    main()
