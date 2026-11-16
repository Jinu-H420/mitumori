"""曲げ工賃の計算（曲げ見積り計算書.html と同じ計算を Python で行う）

標準ライブラリだけで動く。pip install は不要。

  python bend_calc.py --test                     動作確認（答えの分かっている例で検算）
  python bend_calc.py --shape L曲げ --t 6 --tate 500 --yoko 1500 --qty 3
  python bend_calc.py 明細.csv -o 明細_calc.csv   まとめて計算

Python から使う場合:
  import bend_calc as b
  r = b.keisan(shape='コの字曲げ', t=4.5, tate=400, yoko=2000, qty=2, options=['中押し'])
  print(r['total'], r['breakdown'])
"""
import argparse, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'bend_tables.json'), encoding='utf-8'))

SHAPES = sorted({r['shape'] for r in T['bending_table']}) + ['複数曲げ']
SHIMA_SHAPES = sorted({r['shape'] for r in T['shima_table']})
OPT_ALIAS = {'中押し': 'nakagoshi', '中越し': 'nakagoshi', '逆曲げ': 'reverse', '長尺目押し': 'long',
             '長尺': 'long', 'ブロック': 'block', '深曲げ': 'block', 'ハゼ折': 'hazeri', 'はぜ折': 'hazeri'}


def yocho(t):
    """板厚から余長(mm)。縦横それぞれに足す。"""
    for limit, y in T['yocho']:
        if t <= limit:
            return y
    return T['yocho'][-1][1]


def juryo(t, tate, yoko, shima=False, yocho_mm=None):
    """重量(kg)。縞板は板厚ごとの単位重量(kg/m2)、それ以外は 板厚×面積×7.85。"""
    y = yocho(t) if yocho_mm is None else yocho_mm
    a, b = tate + y, yoko + y
    if shima:
        unit = T['shima_unit_weights'].get(str(t)) or T['shima_unit_weights'].get(f'{float(t):.1f}')
        if unit is None:
            raise ValueError(f'縞板に板厚 {t}mm の単位重量がありません（{", ".join(T["shima_unit_weights"])}）')
        return round(unit * a * b / 1e6, 2)
    return round(t * a * b * 7.85 / 1e6, 2)


def qty_factor(qty, qf=None):
    q = dict(T['qty_factor'], **(qf or {}))
    if qty <= q['thresh1']:
        return q['factor1']
    if qty <= q['thresh2']:
        return q['factor2']
    return q['factor3']


def hikiate(shape, weight, length, shima=False):
    """表引き：重量は「入力以上の最小の行」、長さは「入力以下の最小のしきい値の列」。"""
    table = T['shima_table'] if shima else T['bending_table']
    sh = 'C型曲げ' if (not shima and shape == '複数曲げ') else shape
    rows = sorted([r for r in table if r['shape'] == sh], key=lambda r: r['w'])
    if not rows:
        raise ValueError(f'価格表に「{sh}」がありません（使えるのは {"、".join(SHIMA_SHAPES if shima else SHAPES)}）')
    row = next((r for r in rows if r['w'] >= weight), rows[-1])
    th = T['length_thresholds']
    col = next((i for i, v in enumerate(th) if length <= v), len(th) - 1)
    return row['c'][col], ('150kg超' if row['w'] >= 9999 else f'〜{row["w"]}kg'), T['length_labels'][col]


def _apply(v, opt, spec):
    """オプション適用。mult は掛け算、add は足し算。いずれも整数に丸める。"""
    if spec['type'] == 'mult':
        add = round(v * spec['value']) - v
        return v + add, add
    return v + round(spec['value']), round(spec['value'])


def keisan(shape, t=None, tate=None, yoko=None, qty=1, weight=None, length=None,
           shima=False, komono=False, bend_count=None, options=(), use_qty_factor=False,
           yocho_mm=None, qf=None, length_source='W'):
    """曲げ工賃を出す。戻り値は {'total': 1個あたりの円, 'breakdown': 内訳, ...}。

    weight / length を直接渡せば寸法なしでも計算できる（寸法があれば自動で出す）。
    曲げ長さは既定で横(W)。縦を使うなら length_source='L'。
    options は ['中押し','逆曲げ','長尺目押し','ブロック','ハゼ折'] の日本語名で渡す。
    """
    if weight is None or length is None:
        if t is None or tate is None or yoko is None:
            raise ValueError('板厚・縦・横（または 重量・曲げ長さ）が要ります')
        if weight is None:
            weight = juryo(t, tate, yoko, shima, yocho_mm)
        if length is None:
            length = tate if length_source == 'L' else yoko
    steps, total_opts = [], {}

    if komono:
        # 小物の曲げ回数は形状で決まる（複数曲げのときだけ指定できる）
        n = int(bend_count or 4) if shape == '複数曲げ' else T['shape_bend_count'].get(shape, bend_count or 4)
        n = min(8, max(1, int(n)))
        base = T['komono_table'][str(n)]
        f = qty_factor(qty, qf) if use_qty_factor else 1.0
        v = max(T['komono_min'], round(base * f))
        steps.append(f'小物・曲げ{n}回の基準 {base:,}円' + (f' × 数量係数{f}' if use_qty_factor else '')
                     + f' → {v:,}円（1個あたり最低{T["komono_min"]}円）')
        specs = T['komono_options']
        ref = f'小物（曲げ{n}回）'
    else:
        base, w_label, l_label = hikiate(shape, weight, length, shima)
        steps.append(f'{shape}・{w_label}・{l_label} の表引き {base:,}円')
        if not shima and shape == '複数曲げ':
            n = min(8, max(1, int(bend_count or 4)))
            adj = round(base * (n / 4))
            steps.append(f'複数曲げ：C型4回を基準に {base:,}円 × {n}回 ÷ 4回 = {adj:,}円')
            base = adj
        f = qty_factor(qty, qf) if use_qty_factor else 1.0
        v = round(base * f)
        if use_qty_factor:
            steps.append(f'数量{qty}個の係数 ×{f} → {v:,}円')
        specs = T['options']
        ref = f'{shape}（{(T["shima_shape_bend_count"] if shima else T["shape_bend_count"]).get(shape, "?")}回）'

    for name in options:
        key = OPT_ALIAS.get(name, name)
        spec = specs.get(key)
        if spec is None:
            raise ValueError(f'「{name}」は{"小物では" if komono else ""}使えません（{"、".join(s["label"] for s in specs.values())}）')
        if key == 'long' and length < spec.get('min_length_mm', 0):
            steps.append(f'{spec["label"]}：曲げ長さ{length}mm は {spec["min_length_mm"]}mm 未満なので付かない')
            continue
        v, add = _apply(v, key, spec)
        total_opts[spec['label']] = add
        steps.append(f'{spec["label"]}（{"×" + str(spec["value"]) if spec["type"] == "mult" else "+" + str(int(spec["value"])) + "円"}）'
                     f' +{add:,}円 → {v:,}円')

    return {'total': v, 'unit': v, 'sum': v * qty, 'weight': weight, 'length': length,
            'base': base, 'qty': qty, 'ref': ref, 'options': total_opts, 'breakdown': steps}


def main():
    p = argparse.ArgumentParser(description='曲げ工賃の計算（曲げ見積り計算書と同じ）')
    p.add_argument('csv', nargs='?', help='まとめて計算するCSV（列: 形状,板厚,縦,横,数量,材質,曲げ回数,オプション）')
    p.add_argument('-o', '--out', help='CSVの出力先')
    p.add_argument('--shape'), p.add_argument('--t', type=float), p.add_argument('--tate', type=float)
    p.add_argument('--yoko', type=float), p.add_argument('--qty', type=int, default=1)
    p.add_argument('--weight', type=float), p.add_argument('--length', type=float)
    p.add_argument('--bend-count', type=int), p.add_argument('--opt', action='append', default=[])
    p.add_argument('--shima', action='store_true', help='縞板（CHP）')
    p.add_argument('--komono', action='store_true', help='小物モード')
    p.add_argument('--qty-factor', action='store_true', help='数量係数を反映する（既定は反映しない）')
    p.add_argument('--test', action='store_true', help='答えの分かっている例で検算')
    a = p.parse_args()

    if a.test:
        return test()

    if a.csv:
        rows, out = list(csv.DictReader(open(a.csv, encoding='utf-8-sig'))), []
        for row in rows:
            r = keisan(shape=row.get('形状'), t=float(row['板厚']), tate=float(row['縦']), yoko=float(row['横']),
                       qty=int(row.get('数量') or 1), shima=(row.get('材質') or '') in ('縞板', 'CHP'),
                       komono=(row.get('小物') or '') in ('○', 'o', '1'),
                       bend_count=int(row['曲げ回数']) if row.get('曲げ回数') else None,
                       options=[x for x in (row.get('オプション') or '').replace('、', ',').split(',') if x.strip()])
            out.append(dict(row, 重量=r['weight'], 単価=r['total'], 合計=r['sum'], 内訳='／'.join(r['breakdown'])))
        dest = a.out or (os.path.splitext(a.csv)[0] + '_calc.csv')
        with open(dest, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader(), w.writerows(out)
        print(f'{len(out)}件 計算して {dest} に書きました')
        return

    if not a.shape and not a.komono:
        p.error('--shape（形状）か --komono が要ります。形状: ' + '、'.join(SHAPES))
    r = keisan(shape=a.shape, t=a.t, tate=a.tate, yoko=a.yoko, qty=a.qty, weight=a.weight, length=a.length,
               shima=a.shima, komono=a.komono, bend_count=a.bend_count, options=a.opt, use_qty_factor=a.qty_factor)
    print(f'重量 {r["weight"]}kg / 曲げ長さ {int(r["length"])}mm / {r["ref"]}')
    for s in r['breakdown']:
        print('  ' + s)
    print(f'曲げ工賃 {r["total"]:,}円（1個あたり・税抜）　×{r["qty"]}個 = {r["sum"]:,}円')


def test():
    """計算書で確かめた例。ずれたら表か計算が変わっている。"""
    # 期待値は 曲げ見積り計算書.html に同じ条件を入れて読み取った実測値（2026-11-16 照合）
    cases = [
        ('L曲げ t6 500×1500', dict(shape='L曲げ', t=6, tate=500, yoko=1500), 37.23, 2000),
        ('コの字 t4.5 400×2000', dict(shape='コの字曲げ', t=4.5, tate=400, yoko=2000), 29.97, 2300),
        ('四方曲げ t3.2 900×1000（余長30）', dict(shape='四方曲げ', t=3.2, tate=900, yoko=1000), 24.06, 4800),
        ('＋中押し（×1.5）', dict(shape='L曲げ', t=6, tate=500, yoko=1500, options=['中押し']), 37.23, 3000),
        ('＋ハゼ折（+2000）', dict(shape='L曲げ', t=6, tate=500, yoko=1500, options=['ハゼ折']), 37.23, 4000),
        ('長尺目押しは1000mm未満だと付かない', dict(shape='L曲げ', t=6, tate=300, yoko=600, options=['長尺目押し']), 9.34, 500),
        ('長尺目押し 1200mm（+2500）', dict(shape='L曲げ', t=6, tate=300, yoko=1200, options=['長尺目押し']), 18.39, 3500),
        ('数量3個 係数ON（×1.5）', dict(shape='L曲げ', t=6, tate=500, yoko=1500, qty=3, use_qty_factor=True), 37.23, 3000),
        ('数量20個 係数ON（×0.8）', dict(shape='L曲げ', t=6, tate=500, yoko=1500, qty=20, use_qty_factor=True), 37.23, 1600),
        ('複数曲げ6回（C型4回×6/4）', dict(shape='複数曲げ', t=6, tate=500, yoko=1500, bend_count=6), 37.23, 7500),
        ('小物 L曲げ（回数は形状から1回）', dict(shape='L曲げ', t=1.6, tate=100, yoko=300, komono=True), 0.66, 400),
        ('小物 複数曲げ4回', dict(shape='複数曲げ', t=1.6, tate=100, yoko=300, komono=True, bend_count=4), 0.66, 800),
        ('小物 50個 係数ON（×0.8）', dict(shape='L曲げ', t=1.6, tate=100, yoko=300, komono=True, qty=50,
                                          use_qty_factor=True), 0.66, 320),
        ('縞板 L曲げ（短）t4.5 300×1200', dict(shape='L曲げ（短）', t=4.5, tate=300, yoko=1200, shima=True), 14.44, 1000),
    ]
    ng = 0
    for name, kw, w_want, want in cases:
        r = keisan(**kw)
        ok = r['total'] == want and abs(r['weight'] - w_want) < 0.02
        ng += not ok
        print(('  OK  ' if ok else '  NG  ') + f'{name}: {r["weight"]}kg {r["total"]:,}円'
              + ('' if ok else f'（計算書は {w_want}kg {want:,}円）'))
    print(f'{len(cases) - ng}/{len(cases)} 一致')
    sys.exit(1 if ng else 0)


if __name__ == '__main__':
    main()
