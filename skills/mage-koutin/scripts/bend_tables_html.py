"""曲げ見積り計算書.html の中身（文字列）から単価表を取り出す。

bend_calc.py（実行時に最新の計算書を読む）と tools/export_bend_tables.py（同梱用 json を作る）の
両方がこれを使う。取り出し方を1か所にまとめておくため、ここ以外で HTML を読まないこと。

価格表・小物単価・縞板の単位重量に加えて、画面のオプション欄・数量係数欄の初期値も読む。
HTMLの書き方が変わって読めないときは ValueError を出す（呼び出し側が同梱 json に切り替える）。
"""
import re

LENGTH_LABELS = ['〜835mm', '〜1670mm', '〜2505mm', '〜3048mm', '3048mm超']


def _block(src, name):
    parts = src.split('var ' + name)
    if len(parts) < 2:
        raise ValueError(f'計算書に {name} が見つかりません')
    return parts[1]


def _rows(body):
    return [{'shape': s, 'w': int(w), 'c': [int(x) for x in c.split(',')]}
            for s, w, c in re.findall(r"\{shape:'([^']+)',w:(\d+),\s*c:\[([^\]]+)\]\}", body)]


def _obj(src, name):
    body = _block(src, name).split('}')[0]
    return {k.strip().strip("'\""): float(v) for k, v in re.findall(r"'?([\w.（）/]+)'?\s*:\s*([\d.]+)", body)}


def _input(src, id_):
    m = re.search(r'id="' + re.escape(id_) + r'" value="([\d.]+)"', src)
    if not m:
        raise ValueError(f'計算書に入力欄 {id_} の初期値が見つかりません')
    return float(m.group(1))


def _opt(src, id_, label, **extra):
    """オプション欄：先頭の選択肢（mult=× / add=+）と初期値を読む。"""
    m = re.search(r'<select id="' + re.escape(id_) + r'-type"[^>]*><option value="(mult|add)"', src)
    if not m:
        raise ValueError(f'計算書にオプション欄 {id_} が見つかりません')
    v = _input(src, id_ + '-val')
    return dict({'label': label, 'type': m.group(1), 'value': v if m.group(1) == 'mult' else int(v)}, **extra)


def tables_from_html(src):
    """計算書HTMLの文字列 → bend_tables.json と同じ形の dict。読めなければ ValueError。"""
    th = [int(x) for x in re.findall(r'\d+', _block(src, 'LENGTH_THRESHOLDS').split(']')[0])]
    m = re.search(r'Math\.max\((\d+),\s*Math\.round\(unitAfterQty\)\)', src)
    data = {
        '_出どころ': '曲げ見積り計算書.html（価格の正本）。tools/export_bend_tables.py で自動生成。手で編集しない。',
        'length_thresholds': th,
        'length_labels': LENGTH_LABELS,
        'bending_table': _rows(_block(src, 'BENDING_TABLE').split('];')[0]),
        'shima_table': _rows(_block(src, 'SHIMA_TABLE').split('];')[0]),
        'shima_unit_weights': _obj(src, 'SHIMA_UNIT_WEIGHTS'),
        'shape_bend_count': {k: int(v) for k, v in _obj(src, 'SHAPE_BEND_COUNT =').items()},
        'shima_shape_bend_count': {k: int(v) for k, v in _obj(src, 'SHIMA_SHAPE_BEND_COUNT').items()},
        'komono_table': {k: int(v) for k, v in _obj(src, 'KOMONO_DEFAULT_TABLE').items()},
        'komono_min': int(m.group(1)) if m else 300,
        'komono_limit': {'weight_kg': 5.0, 'length_mm': 835},
        'density': 7.85,
        'yocho': [[2.3, 50], [3.2, 30], [99, 20]],
        'qty_factor': {
            'thresh1': int(_input(src, 'qf-thresh1')), 'thresh2': int(_input(src, 'qf-thresh2')),
            'factor1': _input(src, 'qf-factor1'), 'factor2': _input(src, 'qf-factor2'),
            'factor3': _input(src, 'qf-factor3'),
        },
        'options': {
            'nakagoshi': _opt(src, 'opt-nakagoshi', '中押し'),
            'reverse':   _opt(src, 'opt-reverse', '逆曲げ'),
            'long':      _opt(src, 'opt-long-meoshi', '長尺目押し', min_length_mm=1000),
            'block':     _opt(src, 'opt-fukabori', 'ブロック'),
            'hazeri':    _opt(src, 'opt-hazeri', 'ハゼ折'),
        },
        'komono_options': {
            'nakagoshi': _opt(src, 'komono-opt-nakagoshi', '中押し'),
            'reverse':   _opt(src, 'komono-opt-reverse', '逆曲げ'),
            'hazeri':    _opt(src, 'komono-opt-hazeri', 'ハゼ折'),
        },
    }
    check(data)
    return data


def check(data):
    """読み取った表の形を確かめる。おかしければ ValueError。"""
    n = len(data['length_thresholds'])
    if n != len(LENGTH_LABELS):
        raise ValueError(f'長さ区分が {n} 個です（想定は {len(LENGTH_LABELS)} 個）')
    for key, want in [('bending_table', 56), ('shima_table', None)]:
        got = data[key]
        if not got or (want and len(got) != want):
            raise ValueError(f'{key} の行数が想定と違います（{len(got)}行）。HTMLの書き方が変わっていないか確認すること。')
        bad = [r for r in got if len(r['c']) != n]
        if bad:
            raise ValueError(f'{key} の「{bad[0]["shape"]} {bad[0]["w"]}kg」の列数が {len(bad[0]["c"])} です（想定は {n}）')
    if sorted(data['komono_table'], key=int) != [str(i) for i in range(1, 9)]:
        raise ValueError('小物の単価表（KOMONO_DEFAULT_TABLE）が1〜8回になっていません')
    if not data['shima_unit_weights'] or not data['shape_bend_count']:
        raise ValueError('縞板の単位重量か形状ごとの曲げ回数が読めません')
