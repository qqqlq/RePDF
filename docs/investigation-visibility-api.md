# 調査: PyMuPDF で不可視テキストを判定する API

Phase 1 の可視判定（`visibility.py`）を実装する前に、PyMuPDF 1.28.2 で実際に何が
取得できるかを実測した記録。テストコードは `.venv/bin/python3` での対話実行。

## 結論

- パッケージ名は `fitz` ではなく `pymupdf` を使う（`fitz` は非推奨警告が出る。
  中身は同じだが将来削除される）
- `page.get_text("rawdict")` の span には render_mode が含まれない
  （`alpha` が render_mode=3 のとき 0 になる挙動が見えたが、これは内部変換の副作用と
  思われ、信頼して判定根拠にはしない）
- **`page.get_texttrace()` の span の `type` キーが PDF の `Tr` 演算子（レンダリングモード）
  そのものだった。** これが可視判定の主軸になる

## `get_texttrace()` の span で使えるフィールド

| キー | 用途 |
|---|---|
| `type` | レンダリングモード。`0`=塗り(可視) `1`=線 `2`=塗り+線 `3`=**不可視** `4`〜`6`=クリップ付き（見た目には描画される） `7`=クリップのみ（**不可視**） |
| `color` | RGB (0.0–1.0)。背景色（多くは白 `(1,1,1)`）と一致する場合は事実上不可視 |
| `opacity` | 0 なら不可視 |
| `size` | フォントサイズ。極小値は事実上不可視として扱う |
| `bbox` | 文字単位でも `chars` に個別 bbox あり。CropBox 外かどうかの判定に使う |

## `visibility.py` の判定方針（確定）

以下のいずれかに該当したら不可視として除外する（安全側に倒す・OR条件）:

1. `type in (3, 7)`
2. `opacity == 0`
3. `color` が背景色と一致（背景色はページ全体の支配色から推定するか、まずは白固定で開始）
4. `size` が閾値未満（暫定 1.0pt）
5. `bbox` が `page.cropbox` と重ならない

## メタデータ削除

```python
doc.set_metadata({})
doc.del_xml_metadata()  # 存在確認済み。XML形式のメタデータ(XMPなど)も消せる
```

## ラスタライズ

```python
page.get_pixmap(dpi=150)  # dpi指定でそのまま解像度が変わることを確認済み
```
