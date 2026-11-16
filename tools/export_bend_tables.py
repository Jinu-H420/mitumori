"""曲げ見積り計算書.html から単価表を取り出して、スキル用の bend_tables.json を作る。

価格の正本は 曲げ見積り計算書.html の定数（CLAUDE.md 参照）。手で書き写さず、必ずこれで写す。

  python tools/export_bend_tables.py

出力: skills/mage-koutin/scripts/bend_tables.json（計算用）
      skills/mage-koutin/references/parameters.md（人が読む一覧。中身は同じ）
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SRC = os.path.join(PROJ, '曲げ見積り計算書.html')
OUT = os.path.join(PROJ, 'skills', 'mage-koutin', 'scripts', 'bend_tables.json')
OUT_MD = os.path.join(PROJ, 'skills', 'mage-koutin', 'references', 'parameters.md')

def block(src, name):
    return src.split('var ' + name)[1].split('];')[0]

def rows(body):
    return [{'shape': s, 'w': int(w), 'c': [int(x) for x in c.split(',')]}
            for s, w, c in re.findall(r"\{shape:'([^']+)',w:(\d+),\s*c:\[([^\]]+)\]\}", body)]

def obj(src, name):
    body = src.split('var ' + name)[1].split('}')[0]
    # 名前に「/」や（）が入る形状（'コ/Z（両端短）' など）も落とさないよう、引用符つきは中身を丸ごと取る
    return {(q or b): float(v)
            for q, b, v in re.findall(r"(?:'([^']+)'|([\w.]+))\s*:\s*([\d.]+)", body)}

def yen(n):
    return f'{n:,}'


def price_tables(table, labels):
    """形状ごとに「重量 × 曲げ長さ」の表を作る。"""
    out, shapes = [], []
    for r in table:
        if r['shape'] not in shapes:
            shapes.append(r['shape'])
    for s in shapes:
        rs = [r for r in table if r['shape'] == s]
        out += [f'### {s}', '', '| 重量 ＼ 曲げ長さ | ' + ' | '.join(labels) + ' |',
                '|:---|' + '---:|' * len(labels)]
        for i, r in enumerate(rs):
            name = f'{rs[i - 1]["w"]}kg超' if r['w'] >= 9999 and i else f'〜{r["w"]}kg'
            out.append(f'| {name} | ' + ' | '.join(yen(x) for x in r['c']) + ' |')
        out.append('')
    return out


def markdown(d):
    """人が読める一覧（スキルの references/parameters.md）。json と同じ中身。"""
    L = ['# 曲げ工賃のパラメーター一覧（全部）', '',
         '曲げ見積り計算書.html（価格の正本）から自動で作ったもの。**手で直さない。**',
         '直すときは HTML を直して `python tools/export_bend_tables.py`。',
         '金額はすべて 1個あたり・税抜・円。', '',
         '## 1. 重量の出し方', '',
         f'- 通常鋼板: 板厚 ×（縦＋余長）×（横＋余長）× {d["density"]} ÷ 1,000,000（kg）',
         '- 縞板: 単位重量（kg/m²）×（縦＋余長）×（横＋余長）÷ 1,000,000（kg）', '',
         '| 板厚 | 余長（縦・横それぞれ） |', '|:---|---:|']
    prev = None
    for t, y in d['yocho']:
        name = f'{t}mm 以下' if prev is None else (f'{prev}mm 超' if t >= 99 else f'{prev}mm 超 〜 {t}mm')
        L.append(f'| {name} | {y}mm |')
        prev = t
    L += ['', '| 縞板の板厚 | 単位重量（kg/m²） |', '|:---|---:|']
    L += [f'| {k} | {v} |' for k, v in d['shima_unit_weights'].items()]
    L += ['', '## 2. 曲げ回数（形状から決まる）', '', '| 形状 | 回数 |', '|:---|---:|']
    L += [f'| {k} | {v} |' for k, v in d['shape_bend_count'].items()]
    L += [f'| 縞板 {k} | {v} |' for k, v in d['shima_shape_bend_count'].items()]
    L += ['', '複数曲げは C型曲げ（4回）の表を使い、表の値 × 回数 ÷ 4。', '',
          '## 3. 表の引き方', '',
          '- 重量: 入力以上の最小の行', '- 曲げ長さ: 入力以上の最小の列（既定は横の寸法）', '',
          '## 4. 単価表（通常鋼板）', ''] + price_tables(d['bending_table'], d['length_labels'])
    L += ['## 5. 単価表（縞板 CHP）', ''] + price_tables(d['shima_table'], d['length_labels'])
    q = d['qty_factor']
    L += ['## 6. 数量係数（既定は使わない）', '', '| 数量 | 係数 |', '|:---|---:|',
          f'| 1〜{q["thresh1"]}個 | ×{q["factor1"]} |',
          f'| {q["thresh1"] + 1}〜{q["thresh2"]}個 | ×{q["factor2"]} |',
          f'| {q["thresh2"] + 1}個〜 | ×{q["factor3"]} |', '',
          '## 7. オプション（上から順に適用）', '', '| オプション | 効き方 | 条件 |', '|:---|---:|:---|']
    for o in d['options'].values():
        how = f'×{o["value"]}' if o['type'] == 'mult' else f'+{yen(o["value"])}円'
        cond = f'曲げ長さ {yen(o["min_length_mm"])}mm 以上のときだけ' if o.get('min_length_mm') else ''
        L.append(f'| {o["label"]} | {how} | {cond} |')
    k = d['komono_limit']
    L += ['', '## 8. 小物モード', '',
          f'- 使える条件: 重量 {k["weight_kg"]}kg 以下 かつ 曲げ長さ {k["length_mm"]}mm 以下',
          f'- 数量係数をかけたあと、1個あたり最低 {yen(d["komono_min"])}円',
          '- オプションは ' + '・'.join(o['label'] for o in d['komono_options'].values()) + ' だけ', '',
          '| 曲げ回数 | 単価 |', '|:---|---:|']
    L += [f'| {n}回 | {yen(v)} |' for n, v in d['komono_table'].items()]
    return '\n'.join(L) + '\n'


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
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, 'w', encoding='utf-8', newline='\n').write(markdown(data))
    print(f'{OUT_MD} を作りました')
    print(f'{OUT} を作りました（通常 {len(data["bending_table"])}行 / 縞板 {len(data["shima_table"])}行 / '
          f'小物 {len(data["komono_table"])}段 / 形状 {len(data["shape_bend_count"])}種）')

if __name__ == '__main__':
    main()
