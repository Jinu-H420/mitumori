#!/usr/bin/env python3
"""
曲げ見積り evals 実行: evals.json の各ケースで計算し、期待値と比較する。
実行: python3 run_evals.py（evals/ から）または python3 evals/run_evals.py（スキルルートから）
"""
import json
import os

EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(EVALS_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")


def load_data():
    with open(os.path.join(DATA_DIR, "prices.json"), encoding="utf-8") as f:
        prices = json.load(f)
    with open(os.path.join(DATA_DIR, "rates.json"), encoding="utf-8") as f:
        rates = json.load(f)
    return prices, rates


def calc_weight(展開幅_mm, 製品長さ_mm, 板厚_mm, 比重):
    return (展開幅_mm / 1000) * (製品長さ_mm / 1000) * (板厚_mm / 1000) * (比重 * 1000)


def get_base_price(重量_kg, 製品長さ_mm, prices):
    """estimate_bending.py と同じ: 重量・長さそれぞれ「最初に値以上になる区分」を使う"""
    w = prices["重量区分"]
    l = prices["長さ区分"]
    # 重量: 最初の w[i] で 重量_kg <= w[i] となる行
    row = len(w) - 1
    for i, t in enumerate(w):
        if 重量_kg <= t:
            row = i
            break
    # 長さ: 最初の l[j] で 製品長さ_mm <= l[j] となる列
    col = len(l) - 1
    for j, t in enumerate(l):
        if 製品長さ_mm <= t:
            col = j
            break
    row = min(row, len(prices["基準価格"]) - 1)
    col = min(col, len(prices["基準価格"][0]) - 1)
    return prices["基準価格"][row][col]


def get_qty_rate(数量, rates):
    for row in rates["数量調整"]:
        if row["min"] <= 数量 and (row["max"] is None or 数量 <= row["max"]):
            return row["rate"]
    return 1.0


def calc_見積り_税抜(input_data, prices, rates):
    """穴あけ加算なしで単価×数量を返す（evals の expected と比較用）"""
    shape = input_data["形状"]
    thickness = input_data["板厚_mm"]
    width = input_data["展開幅_mm"]
    length = input_data["製品長さ_mm"]
    material = input_data["材質"]
    qty = input_data["数量"]

    gravity = rates["比重"].get(material)
    if gravity is None:
        raise ValueError(f"未知の材質: {material}")

    weight = calc_weight(width, length, thickness, gravity)
    base = get_base_price(weight, length, prices)
    shape_rate = rates["形状乗率"].get(shape)
    if shape_rate is None:
        raise ValueError(f"未知の形状: {shape}")
    qty_rate = get_qty_rate(qty, rates)

    raw = base * shape_rate * qty_rate
    # 100円単位に丸め（計算書と同じ）
    if int(raw) % 50 == 0:
        unit_price = int(raw)
    else:
        unit_price = round(raw / 100) * 100
    見積り_税抜 = unit_price * qty

    return {
        "重量_kg": round(weight, 3),
        "基準価格": base,
        "形状乗率": shape_rate,
        "数量調整": qty_rate,
        "単価_税抜": unit_price,
        "見積り_税抜": 見積り_税抜,
    }


def main():
    prices, rates = load_data()
    evals_path = os.path.join(EVALS_DIR, "evals.json")
    with open(evals_path, encoding="utf-8") as f:
        cases = json.load(f)

    ok = 0
    ng = 0
    for c in cases:
        name = c["name"]
        try:
            got = calc_見積り_税抜(c["input"], prices, rates)
            exp = c["expected"]
            # 見積り_税抜が一致すればOK（中間値は参考表示）
            if got["見積り_税抜"] == exp["見積り_税抜"]:
                print(f"OK  {name}")
                ok += 1
            else:
                print(f"NG  {name}  期待={exp['見積り_税抜']}  実際={got['見積り_税抜']}")
                ng += 1
        except Exception as e:
            print(f"ERR {name}  {e}")
            ng += 1

    print("---")
    print(f"合計: {ok} 成功, {ng} 失敗")
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    exit(main())
