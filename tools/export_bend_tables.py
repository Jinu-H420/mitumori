"""曲げ見積り計算書.html から単価表を取り出して、スキル用の bend_tables.json を作る。

価格の正本は 曲げ見積り計算書.html の定数（CLAUDE.md 参照）。手で書き写さず、必ずこれで写す。

  python tools/export_bend_tables.py

出力: skills/mage-koutin/scripts/bend_tables.json

この json は「ネットに出られない環境」用の控え。スキルはふだん最新の計算書を直接読むので、
これを作り直し忘れても計算はずれない。main に計算書の変更が入ると GitHub Actions
（.github/workflows/mage-koutin.yml）が自動で作り直してコミットする。
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SRC = os.path.join(PROJ, '曲げ見積り計算書.html')
SCRIPTS = os.path.join(PROJ, 'skills', 'mage-koutin', 'scripts')
OUT = os.path.join(SCRIPTS, 'bend_tables.json')

sys.path.insert(0, SCRIPTS)
from bend_tables_html import tables_from_html  # noqa: E402  取り出し方はスキルと共通


def main():
    try:
        data = tables_from_html(open(SRC, encoding='utf-8').read())
    except ValueError as e:
        raise SystemExit(f'計算書から単価表を読めませんでした: {e}')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'{OUT} を作りました（通常 {len(data["bending_table"])}行 / 縞板 {len(data["shima_table"])}行 / '
          f'小物 {len(data["komono_table"])}段 / 形状 {len(data["shape_bend_count"])}種）')


if __name__ == '__main__':
    main()
