# -*- coding: utf-8 -*-
"""
曲げ加工見積もりシステム v2.1 — 加工工賃のみの計算ロジック
bending_price_table.csv と板厚別ピアス単価を使用。
"""

import csv
import json
import os
from typing import Any, List, Dict, Optional

# 長さ列の上限 (mm)。ヘッダー 〜835mm, 〜1670mm, 〜2505mm, 〜3048mm, 3048mm超
LENGTH_COLUMNS = ["〜835mm", "〜1670mm", "〜2505mm", "〜3048mm", "3048mm超"]
LENGTH_THRESHOLDS = [835, 1670, 2505, 3048, 99999]

# ピアス単価: 板厚 t (mm) → 円/個
def pierce_price_for_thickness(t: float) -> int:
    if t <= 2.3:
        return 30
    if t <= 4.5:
        return 60
    if t <= 9.0:
        return 100
    if t <= 12.0:
        return 150
    return 200

# レーザーポンチ単価
PUNCH_PRICE = 30

# 数量スライド: 1-4 → 1.5, 5-19 → 1.0, 20+ → 0.8
def quantity_factor(lot: int) -> float:
    if lot <= 4:
        return 1.5
    if lot <= 19:
        return 1.0
    return 0.8

# 小物割引: 長辺<=300 かつ 重量<=1.0 → 0.8、曲げ工賃下限300円
BENDING_FLOOR = 300
SMALL_PART_DISCOUNT = 0.8


def load_price_table(path: str) -> List[Dict]:
    """CSV を読み込み、形状・重量範囲で検索可能な行リストを返す。"""
    rows = []
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            row["重量範囲"] = int(row["重量範囲"])
            for col in LENGTH_COLUMNS:
                row[col] = int(row[col])
            rows.append(row)
    return rows


def get_base_price(
    table: list[dict],
    shape: str,
    weight_kg: float,
    length_mm: float,
) -> tuple:
    """
    形状・重量・長さに合致する基準価格を取得。
    戻り値: (価格, 採用した重量クラス, 採用した長さクラス)
    重量: 入力重量 <= テーブル重量 となる最小の行
    長さ: 入力長さ <= テーブル長さ となる最小の列
    """
    # 形状でフィルタ
    by_shape = [r for r in table if r["形状"] == shape]
    if not by_shape:
        raise ValueError(f"形状が見つかりません: {shape}")

    # 重量: 重量範囲 >= weight となる最小の行
    by_shape.sort(key=lambda r: r["重量範囲"])
    row = None
    for r in by_shape:
        if r["重量範囲"] >= weight_kg:
            row = r
            break
    if row is None:
        row = by_shape[-1]  # 最大重量の行を適用

    # 長さ: 最初に length_mm <= 閾値 となる列
    col_name = LENGTH_COLUMNS[-1]
    for i, thresh in enumerate(LENGTH_THRESHOLDS):
        if length_mm <= thresh:
            col_name = LENGTH_COLUMNS[i]
            break
    price = row[col_name]
    weight_class = f"{row['重量範囲']}kg"
    length_class = col_name
    return price, weight_class, length_class


def calc_bending(
    table: list[dict],
    shape: str,
    weight_kg: float,
    length_mm: float,
    long_side_mm: float,
    lot: int,
    nakagoshi: bool = False,
    reverse_bend: bool = False,
    meoshi_long: bool = False,  # 長尺目押し（長さ>=1000 かつ目押し指定）
    fukabend: bool = False,     # 深曲げ・干渉回避
) -> Dict[str, Any]:
    """
    曲げ加工費を計算。戻り値は breakdown.bending_cost 用の辞書。
    """
    base, weight_class, length_class = get_base_price(table, shape, weight_kg, length_mm)
    qty_f = quantity_factor(lot)
    subtotal = base * qty_f

    complexity = 1.0
    addons = 0
    if nakagoshi:
        complexity *= 1.5
    if reverse_bend:
        complexity *= 1.2
    if meoshi_long and length_mm >= 1000:
        addons += 2500
    if fukabend:
        addons += 3000

    subtotal = subtotal * complexity + addons

    small_f = 1.0
    if long_side_mm <= 300 and weight_kg <= 1.0:
        small_f = SMALL_PART_DISCOUNT
    subtotal = subtotal * small_f
    subtotal = max(BENDING_FLOOR, round(subtotal))

    return {
        "base_price": base,
        "quantity_adjustment": qty_f,
        "complexity_adjustment": complexity,
        "small_part_adjustment": small_f,
        "addons_yen": addons,
        "weight_class": weight_class,
        "length_class": length_class,
        "total": int(subtotal),
    }


def calc_hole_cost(
    thickness_mm: float,
    punch_count: int = 0,
    pierce_count: int = 0,
) -> Dict[str, Any]:
    """穴あけコスト。レーザーポンチ 30円/個、ピアスは板厚別。"""
    pierce_unit = pierce_price_for_thickness(thickness_mm)
    punch_total = punch_count * PUNCH_PRICE
    pierce_total = pierce_count * pierce_unit
    total = punch_total + pierce_total
    return {
        "punch_count": punch_count,
        "punch_price": PUNCH_PRICE,
        "pierce_count": pierce_count,
        "pierce_price": pierce_unit,
        "total": int(total),
    }


def estimate(
    shape: str,
    weight_kg: float,
    length_mm: float,
    long_side_mm: float,
    lot: int,
    thickness_mm: float,
    punch_count: int = 0,
    pierce_count: int = 0,
    nakagoshi: bool = False,
    reverse_bend: bool = False,
    meoshi_long: bool = False,
    fukabend: bool = False,
    table_path: Optional[str] = None,
    tax_rate: float = 0.1,
) -> Dict[str, Any]:
    """
    見積もりを一括計算。加工工賃のみ（材料費含まない）。
    """
    if table_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        table_path = os.path.join(base_dir, "data", "bending_price_table.csv")

    table = load_price_table(table_path)
    bending = calc_bending(
        table, shape, weight_kg, length_mm, long_side_mm, lot,
        nakagoshi=nakagoshi, reverse_bend=reverse_bend,
        meoshi_long=meoshi_long, fukabend=fukabend,
    )
    hole = calc_hole_cost(thickness_mm, punch_count, pierce_count)

    processing_ex = bending["total"] + hole["total"]
    processing_in = int(round(processing_ex * (1 + tax_rate)))

    return {
        "total_estimate": {
            "processing_cost_tax_excluded": processing_ex,
            "processing_cost_tax_included": processing_in,
        },
        "breakdown": {
            "bending_cost": {k: v for k, v in bending.items() if k in ("base_price", "quantity_adjustment", "complexity_adjustment", "small_part_adjustment", "total")},
            "hole_cost": hole,
        },
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="曲げ加工見積もり v2.1")
    p.add_argument("--shape", required=True, help="形状 (L曲げ, コの字曲げ, Z曲げ, C型曲げ, ハット曲げ)")
    p.add_argument("--weight", type=float, required=True, help="重量 kg")
    p.add_argument("--length", type=float, required=True, help="長さ mm")
    p.add_argument("--long-side", type=float, required=True, help="長辺 mm（小物割引判定用）")
    p.add_argument("--lot", type=int, default=1, help="製造個数")
    p.add_argument("--thickness", type=float, required=True, help="板厚 mm")
    p.add_argument("--punch", type=int, default=0, help="レーザーポンチ数")
    p.add_argument("--pierce", type=int, default=0, help="ピアス数")
    p.add_argument("--nakagoshi", action="store_true", help="中押し")
    p.add_argument("--reverse-bend", action="store_true", help="逆曲げ")
    p.add_argument("--meoshi-long", action="store_true", help="長尺目押し")
    p.add_argument("--fukabend", action="store_true", help="深曲げ・干渉回避")
    p.add_argument("--csv", default=None, help="bending_price_table.csv のパス")
    args = p.parse_args()

    result = estimate(
        shape=args.shape,
        weight_kg=args.weight,
        length_mm=args.length,
        long_side_mm=args.long_side,
        lot=args.lot,
        thickness_mm=args.thickness,
        punch_count=args.punch,
        pierce_count=args.pierce,
        nakagoshi=args.nakagoshi,
        reverse_bend=args.reverse_bend,
        meoshi_long=args.meoshi_long,
        fukabend=args.fukabend,
        table_path=args.csv,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
