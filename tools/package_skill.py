"""スキル mage-koutin を、ほかの人に渡せる1つのファイル（配布/mage-koutin.skill）にまとめる。

  python tools/package_skill.py

やること:
  1. 曲げ見積り計算書.html から単価表を作り直す（古い単価のまま配らないため）
  2. 計算書と照合した例を全部確かめる（1つでも合わなければ作らない）
  3. 配布/mage-koutin.skill を作る

受け取った人は、Claude の「設定 → 機能 → スキル」でこのファイルをアップロードすれば使える。
"""
import os, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'skills', 'mage-koutin')
OUT_DIR = os.path.join(ROOT, '配布')
OUT = os.path.join(OUT_DIR, 'mage-koutin.skill')


def run(args):
    r = subprocess.run([sys.executable] + args, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit('途中で失敗したので、配布ファイルは作っていません。')


run([os.path.join('tools', 'export_bend_tables.py')])
run([os.path.join('skills', 'mage-koutin', 'scripts', 'bend_calc.py'), '--test'])

os.makedirs(OUT_DIR, exist_ok=True)
n = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    for d, dirs, files in os.walk(SRC):
        dirs[:] = [x for x in dirs if x != '__pycache__']
        for f in sorted(files):
            if f.endswith('.pyc'):
                continue
            p = os.path.join(d, f)
            rel = os.path.relpath(p, os.path.dirname(SRC)).replace(os.sep, '/')
            z.write(p, rel)
            n += 1
print(f'作りました: {OUT}（{n}ファイル / {os.path.getsize(OUT):,}バイト）')
