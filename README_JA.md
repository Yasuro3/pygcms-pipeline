# PyGCMS Pipeline v1.4.0 — 日本語操作説明

作成日：2026年10月18日。ソフト1.4.0／分類モデル2.2.0／同定QC 1.0.0。
これは生成した配布パッケージです。GitHub・Zenodoにはまだアップロードしていません。

## 今回の変更

既存の候補名・スコア・強度・候補選択理由を残したまま、品質条件で掲載対象を選び、
非芳香族の分類誤りを修正し、分類別応答と検出頻度を再計算します。
ソフトの操作画面・通常のmzML/QGD入力・NISTブリッジは引き継いでいます。
測定済みのスペクトル強度に係数を掛ける補正や、未知物質の確定同定は行いません。

## 最初に開くファイル

ZIPをフォルダごと展開して、Windowsでは `09_OPEN_QC.cmd` をダブルクリックしてください。
または `software/index.html` をChrome／Edgeで直接開きます。
最初の画面にある **Reprocess saved CSV / QC v1.4.0** を押します。
QCだけなら、NISTを立ち上げたりAPIキーを入力したりする必要はありません。

1. **1. Import saved results CSVs**：元の `*_results.csv` を複数選択します。
2. 必要に応じて試料情報表（run manifest）を指定します。
3. MF800・イオン3個・相対応答0.001%を確認し、**2. Run QC** を押します。
4. 件数、各測定の応答保持率、保留候補を確認し、**3. Export complete QC report ZIP** を押します。

`*_TIC_data.csv`、`*_class_summary.csv`、638候補の一覧表は、成分別入力の代わりにはできません。
`TotalIntensity`、`Compound`、`NIST_MF`、`PureIons` 等を含む元の結果CSVを使用してください。
イオン数などの記録が欠けていれば「未記録」とし、推測で通過させません。

## 大きなバッチZIP／多数の測定を一括処理する

過去のバッチZIPは候補説明が長く、展開時に数百MBになることがあります。
その場合はコマンド処理を使う方がメモリー負担を減らせます。
エクスプローラーで本ソフトのフォルダを開き、アドレス欄に `cmd` と入力します。

```text
py -m pip install -r requirements.txt -r requirements-browser.txt
py -m playwright install chromium
py scripts\qc_reprocess.py "C:\解析データ\バッチ.zip" --out "C:\解析結果\QC140"
```

琵琶湖の元ZIPで環境試料60測定だけを選び、検証粉末を除く例：

```text
py scripts\qc_reprocess.py "C:\解析データ\PyGCMS_batch.zip" --pattern "21*_results.csv" --out "C:\解析結果\Biwa_QC140"
```

出力先には新しい空フォルダを指定します。既存の解析結果は上書きしません。
同じ測定を重複読み込みした場合はエラーにし、黙って二重計算しません。
`10_REPROCESS_CSV.cmd` に入力ZIPまたは結果フォルダをドラッグする方法もあります。
実行前にPythonと必要ライブラリを準備してください。

## 試料情報と検出頻度

ファイル名に `_TD_`／`_PY_` と日付・地点・層があれば情報を抽出しますが、
これはファイル名からの推定です。画面からダウンロードできる `QC_Run_Manifest_Template.csv`
に正しい試料情報を入れて読み込むと、明示した値を優先します。
同じ分析条件の試料には同じ `Method_ID` を付けます。異なるGC条件を同じRT比較に入れません。

TD・PYの頻度は、各温度領域で読み込んだ測定数を分母にします。
同一測定内で同じ候補が複数ピークに付いていても頻度は1回です。
Eitherは、TD/PYが一つずつ対応する試料の和集合です。片方が欠ける場合や
同じ試料にTDが複数ある場合を、完全な1組として扱いません。
全く成分がない測定も含める場合は、情報表で `Zero_component_run=true` を明示します。
元の30試料／30 TD・30 PYの構成を使えば、分母もその構成に対応します。

## 閾値の意味

初期値は MF≧800、PureIons≧3、測定内相対応答≧0.001％です。
相対応答の分母は新しい閾値を適用する前の保持成分応答の合計です。
90％は保持率の注意表示であり、90％以上にするため閾値を自動調整しません。
検出頻度90％以上という条件でもありません。

初期値の `JAAP_LEGACY` は、この論文で使った旧除外条件を引き継ぎます。
通常のGC-MSや別の研究では、`NONE / generic` を選び、トルエンを自動的に除外しないでください。
この除外条件はブランクを新たに測定して決めたものではありません。

## 2種類の集計を区別してください

**corrected_candidate_conditional**：品質条件を通った成分を、候補名が正しいという条件付きで
修正後の分類に集計します。原分類、修正後分類、修正理由は別々に残します。

**identity_conservative**：具体名の根拠不足が大きい成分をR（未解決）に回した保守的な集計です。
強度は消さずRに残します。こちらは同定上の制約を厳しく扱う感度解析です。

2種類を混ぜて論文の数値を作らないでください。どちらを主解析に使うか明示します。
既存論文の旧集計を自動的に「正しい最新版」に置き換えたという意味ではありません。
本パッケージ生成では、JAAP原稿の数値・図表そのものは変更していません。

## 化合物名・分類の扱い

異性体は、支持できなければCresol isomer等の表示にします。
分子式と保持時間が近いだけで別の候補IDを統合せず、元の候補一覧を保存します。
同一名が離れた保持時間帯に現れる場合は要確認です。0.12分と0.08分は診断用であり、
全条件に普遍的な保持時間許容差ではありません。

非芳香族ジエン／水素化環を芳香族に数える誤り、非芳香族含酸素化合物をOArに入れる誤り、
長鎖ニトリルを構造上「炭化水素」と呼ぶ誤りなどを明示規則で修正します。
すべての有機分子の構造を自動検証するソフトではありません。

## 生成ファイル

`01_component_QC_audit.csv`：元の列すべて＋新しいQC列。
`02_reported_candidates.csv`：候補別一覧・表示名・分類・頻度。
`03_run_QC_summary.csv`：測定別の分母と保持率。
`04_group_summary.csv`／`05_group_ratios.csv`：分類別応答と比率。
`06_retention_band_diagnostics.csv`：保持時間の診断。
`07_classification_transitions.csv`：分類変更記録。
`08_author_review_queue.csv`：確認が必要な候補。
`09_processing_manifest.json`：条件・版・元ファイルのチェックサム。
`10_printable_inventory.html`：すべての掲載候補を読む表。ブラウザーから印刷・PDF保存できます。

## GitHubへの更新

このZIPは `software`、`scripts`、`tests`、`docs`、`data`、`provenance`、README等を含む一式です。
既存リポジトリに `release-v1.4.0` などの作業ブランチを作り、全フォルダの同じ階層へ反映します。
`.git` は触らず、公開済みv1.3.2のタグ・DOIを上書きしません。
差分一覧は `provenance/v140_changes_from_supplied_base.json` に記録します。
旧READMEや旧検証データは履歴として保持しています。

NIST本体・参照スペクトル・APIキー・リカバリーコード・今回の未投稿論文の生データは、
公開用ソフトZIPに追加しないでください。公開先の書き換えは今回行っていません。

## 検証の範囲

新機能は自動回帰テストと保存済み環境試料で確認し、結果は `VALIDATION_REPORT.md` に記載します。
今回の環境ではWindowsのライセンス付きNIST実行ファイルや実機への接続確認はしていません。
QGDは既存リーダーを保持し、合成した対応レイアウトで回帰試験しています。
すべてのQGD形式への対応や、全候補の確定同定を保証するものではありません。


## Reprocessing a v1.4.0 export / v1.4.0出力の再処理

Do not import a `QC140_*` audit back over itself. For a newly analyzed sample,
use **Component-source CSV** to save a reprocessable snapshot without appended QC
columns. This preserves previous QC outputs rather than overwriting their history.
`QC140_*`列付きの結果は再入力で上書きしません。新規測定の再処理用には、
**Component-source CSV**を保存してください。コマンドではファイルを直接指定するか、
`--pattern "*_component_source.csv"`を指定します。

For the identity-conservative view, any exact-name-withheld occurrence or conflicting
report-group assignment makes the entire candidate key R across the loaded batch.
This keeps the catalogue class and every contributing summary row consistent.
The candidate-conditional view remains separate and does not apply this propagation.
This is a deliberately conservative sensitivity view, not proof all those signals are false.
