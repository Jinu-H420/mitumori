"""曲げ逆算ダッシュボードの更新（トークンを使わない。Python だけで動く）

見積回答アーカイブ（受注・見積自動処理システムが作る items.jsonl）と、
曲げ見積り計算書の実績（GAS）を読み、実績が0〜2件の欄に当たる過去の曲げ見積を
逆算して 曲げ逆算ダッシュボード.html を作り直す。あわせて蓄積の推移を記録する。

  python tools/update_gyakusan.py

出力（どれも得意先名・単価を含むので .gitignore 済み）
  曲げ逆算ダッシュボード.html
  data/gyakusan/candidates.json   … 逆算候補
  data/gyakusan/history.csv       … 実行ごとの蓄積状況（月別件数・空き欄数）
"""
import collections, csv, datetime, json, os, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

# パソコン・アカウントごとに置き場所が違うので、次の順で探す。
#   1. 環境変数 MITUMORI_ARCHIVE / MITUMORI_PDF_ROOT
#   2. tools/paths.json（{"archive": "...", "pdf_root": "..."}）
#   3. 下の候補を上から順に（見つかった最初のもの）
ARCH_CANDIDATES = [
    os.path.join(os.path.expanduser('~'), 'uchino-kanban-estimate', 'data', 'archive', 'items.jsonl'),
    r'C:\Users\Hayato\uchino-kanban-estimate\data\archive\items.jsonl',
]
PDF_CANDIDATES = [
    r'Z:\データフォルダ\社内データ用\70_蓄積データ\50_見積回答',
    r'\\srv02\共有\データフォルダ\社内データ用\70_蓄積データ\50_見積回答',
]

def pick(env, key, candidates, what):
    v = os.environ.get(env)
    if v:
        return v
    try:
        v = json.load(open(os.path.join(HERE, 'paths.json'), encoding='utf-8')).get(key)
        if v:
            return v
    except Exception:
        pass
    for c in candidates:
        if os.path.exists(c):
            return c
    raise SystemExit(
        f'{what}が見つかりません。次のどちらかで場所を教えてください。\n'
        f'  ・環境変数 {env} にパスを入れる\n'
        f'  ・tools/paths.json に {{"{key}": "パス"}} と書く\n'
        f'  探した場所: ' + ' / '.join(candidates))

ARCH = pick('MITUMORI_ARCHIVE', 'archive', ARCH_CANDIDATES, '見積回答データ（items.jsonl）')
PDF_ROOT = pick('MITUMORI_PDF_ROOT', 'pdf_root', PDF_CANDIDATES, '見積回答PDFのフォルダ')
CALC_HTML = os.path.join(PROJ, '曲げ見積り計算書.html')
TEMPLATE = os.path.join(PROJ, '.claude', 'dash_template.html')
OUT_HTML = os.path.join(PROJ, '曲げ逆算ダッシュボード.html')
OUT_DIR = os.path.join(PROJ, 'data', 'gyakusan')

W = [10, 20, 30, 50, 80, 100, 150, 9999]
L = [835, 1670, 2505, 3048, 99999]
ENOUGH = 3  # この件数以上の実績がある欄は候補にしない

def wb(w): return next(t for t in W if w <= t)
def li(l): return next(i for i, t in enumerate(L) if l <= t)
def yocho(t, bonde): return 100 if bonde else 50 if t <= 2.3 else 30 if t <= 3.2 else 20

def load_table(src):
    body = src.split('var BENDING_TABLE')[1].split('];')[0]
    return {(s, int(w)): [int(x) for x in c.split(',')]
            for s, w, c in re.findall(r"\{shape:'([^']+)',w:(\d+),\s*c:\[([^\]]+)\]\}", body)}

def load_have(src):
    url = re.search(r"GAS_API_URL\s*=\s*'([^']+)'", src).group(1)
    recs = json.load(urllib.request.urlopen(url, timeout=60))
    direct, total = collections.Counter(), collections.Counter()  # direct = 社長の直接回答のみ、total = 逆算分も含む
    for x in recs:
        i = x.get('input')
        if not i or i.get('komonoMode') or i.get('material') == 'shima':
            continue
        s = 'C型曲げ' if i.get('shape') == '複数曲げ' else i.get('shape')
        cell = (s, wb(i.get('weight') or 0), li(i.get('bendLength') or 0))
        total[cell] += 1
        if x.get('source') != 'gyakusan':
            direct[cell] += 1
    n_gyk = sum(1 for x in recs if x.get('source') == 'gyakusan')
    n_all = sum(1 for x in recs if x.get('input'))
    return direct, total, n_all - n_gyk, n_gyk

EXCLUDE_MAT = re.compile(r'縞|しま|CHP|SUS|ステン|アルミ|AL|WEL|ハイテン')
EXTRA = re.compile(r'塗装|メッキ|溶接|組|タップ|皿|プレス|R\d|ロール|レーザー|現場|運賃|配送')

def shape_of(x):
    t = (x.get('原文') or '') + ' ' + (x.get('加工') or '')
    for pat, s in [(r'三方|3方', '三方曲げ'), (r'四方|4方|箱', '四方曲げ'), (r'ハット', 'ハット曲げ'),
                   (r'Z曲|Ｚ曲|Z型|Ｚ型|クランク', 'Z曲げ'), (r'C型|Ｃ型|リップ', 'C型曲げ'),
                   (r'コの字|コ字|チャンネル|ｺの字', 'コの字曲げ'), (r'L曲|Ｌ曲|L字|Ｌ字|アングル', 'L曲げ')]:
        if re.search(pat, t):
            return s
    return {1: 'L曲げ', 2: 'コの字曲げ', 3: '三方曲げ', 4: 'C型曲げ'}.get(x.get('曲げ数'))

def pdf_finder():
    names = None
    MARK = '50_見積回答'
    def find(p):
        nonlocal names
        if not p or MARK not in p:
            return ''
        local = os.path.join(PDF_ROOT, p[p.index(MARK) + len(MARK):].lstrip('\\/'))
        if not os.path.exists(local):
            if names is None:  # 移動済みのものだけファイル名で探す（初回のみ全体を走査）
                names = {}
                for d, _, fs in os.walk(PDF_ROOT):
                    for f in fs:
                        names.setdefault(f, os.path.join(d, f))
            local = names.get(os.path.basename(local), '')
        return os.path.relpath(local, PDF_ROOT).replace('\\', '/') if local else ''
    return find

def main():
    src = open(CALC_HTML, encoding='utf-8').read()
    table = load_table(src)
    have, total, n_recs, n_gyk = load_have(src)
    items = [json.loads(l) for l in open(ARCH, encoding='utf-8')]
    months = collections.Counter((x.get('日にち') or '')[:7] for x in items)
    find = pdf_finder()

    rows, seen, bend_total = [], set(), 0
    for x in items:
        if x.get('加工') not in ('曲げ', '箱曲げ', '折曲げ', '板金部品'): continue
        if x.get('回答区分') != '回答済' or not x.get('単価'): continue
        bend_total += 1
        t, a, b = x.get('板厚'), x.get('長辺'), x.get('短辺')
        if not (t and a and b): continue
        text = x.get('原文') or ''
        if EXCLUDE_MAT.search((x.get('材質') or '') + text): continue
        if x.get('加工') == '板金部品' and '曲' not in text: continue
        s = shape_of(x)
        if not s: continue
        bonde = 'ボンデ' in (x.get('材質') or '') + text
        y = yocho(t, bonde)
        wt = t * (a + y) * (b + y) * 7.85 / 1e6
        if wt <= 5 and a <= 835: continue  # 小物モードの範囲
        key = (x['日にち'], x.get('得意先'), x['単価'], text)
        if key in seen: continue
        seen.add(key)
        wbin, lidx = wb(wt), li(a)
        n = have[(s, wbin, lidx)]
        if n >= ENOUGH: continue
        kiriita = wt * (190 if t in (3.2, 4.5) else 185)
        ana = (x.get('穴の数') or 0) * 50
        bend = x['単価'] - kiriita - ana
        extra = list(dict.fromkeys(EXTRA.findall(text)))
        why = []
        if bend <= 0: why.append('逆算がマイナス（材料費より安い）')
        if extra: why.append('曲げ以外の作業あり：' + '・'.join(extra))
        if x.get('要確認'): why.append(x['要確認'])
        rows.append(dict(k='|'.join([x['日にち'], x.get('得意先') or '不明', str(x['単価']), text]),
            shape=s, w=wbin, l=lidx, have=n, date=x['日にち'], cust=x.get('得意先') or '不明',
            t=t, a=a, b=b, qty=x.get('数量'), tanka=x['単価'], wt=round(wt, 1), kiriita=round(kiriita),
            ana=ana, bend=round(bend, -1), table=table[(s, wbin)][lidx], text=text,
            flag='ok' if (bend > 0 and not extra and not x.get('要確認')) else 'chk',
            why=why, pdf=find(x.get('ファイルパス')), bonde=bonde, y=y))

    order = list(dict.fromkeys(s for s, _ in table))
    rows.sort(key=lambda r: (order.index(r['shape']), r['w'], r['l'], r['date']))
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT_DIR, 'candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    tpl = open(TEMPLATE, encoding='utf-8').read()
    gas = re.search(r"GAS_API_URL\s*=\s*'([^']+)'", src).group(1)
    page = tpl.replace('/*DATA*/[]', json.dumps(rows, ensure_ascii=False)).replace('/*GAS*/', gas)
    open(OUT_HTML, 'w', encoding='utf-8').write(page)

    # 空き欄 = 実績が ENOUGH 件未満の欄（通常鋼板7形状×8重量帯×5長さ＝280欄）
    empty = sum(1 for (s, w) in table for l in range(len(L)) if total[(s, w, l)] < ENOUGH)
    span = sorted(m for m in months if re.match(r'\d{4}-\d{2}', m) and months[m] >= 20)
    hist = os.path.join(OUT_DIR, 'history.csv')
    new = not os.path.exists(hist)
    with open(hist, 'a', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(['実行日時', 'データ期間', '月数', '見積明細', '曲げ明細', '社長の実績', '逆算の登録', '足りない欄(280中)', '逆算候補', 'うち使えそう'])
        wr.writerow([datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), f'{span[0]}〜{span[-1]}' if span else '',
                     len(span), len(items), bend_total, n_recs, n_gyk, empty, len(rows), sum(r['flag'] == 'ok' for r in rows)])
    print(f'データ期間 {span[0]}〜{span[-1]}（{len(span)}か月）/ 曲げ明細 {bend_total} / 足りない欄 {empty}/280 / 逆算候補 {len(rows)}（使えそう {sum(r["flag"] == "ok" for r in rows)}）')

if __name__ == '__main__':
    main()
