"""スキル mage-koutin を、このパソコンの ~/.claude/skills/ に入れる（どのチャットでも使えるようにする）。

  python tools/install_skill.py

別のアカウント・別のパソコンでも、リポジトリを取ってきてこれを1回実行すれば使える。
"""
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'skills', 'mage-koutin')
DST = os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'mage-koutin')

if not os.path.isdir(SRC):
    raise SystemExit(f'スキルが見つかりません: {SRC}')
shutil.rmtree(DST, ignore_errors=True)
shutil.copytree(SRC, DST)
print(f'入れました: {DST}\n新しいチャットから「曲げ工賃」と言えば使えます。')
