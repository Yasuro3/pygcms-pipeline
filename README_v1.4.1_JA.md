# Public v1.4.1-rc2: mzML-only

The current experimental public Global NNLS pipeline takes XML mzML data only. Open `pipeline_v141/MZML_ONLY_RELEASE.md` for use and limitations. The v1.4.1-rc1 release below is historical and still contains QGD direct input. Native QGD decoding is reserved for a separate local research build.

---

# PyGCMS Pipeline v1.4.1 — Global NNLS（試験版 / Release Candidate）

**この配布物は、従来のv1.4.0のTIC局所極大方式とは異なる、全成分共通のNNLSデコンボリューションを行うWindows向けソフトウェアです。** QGD原データの読込み、成分モデルの計算、NIST MSP出力、NIST MS Searchとの一括連携、公式分類・QCエンジンでの再集計に対応します。NISTライセンス・ライブラリ自体は同梱しません。

> **研究上の注意**：分離アルゴリズムは開発中の実験実装です。面積二重計上の抑止テストが通っても、化学的分離の正しさ・実成分数・濃度を保証するものではありません。真正NIST AMDISとの4測定の探索的比較は実施済みですが、分離精度の包括的検証およびGCMSsolutionとの独立比較は未完了です。検証が済むまで安定版として論文に断定的に引用しないでください。

## 最初に行う操作（Windows）

GitHubのソースZIPを展開した場合は、先に `pipeline_v141` フォルダーを開いてください。以下の相対パスと起動ファイルはこのフォルダーを基準とします。

1. ZIPを完全に展開し、`00_INSTALL_DEPENDENCIES.cmd` をダブルクリック。WindowsのPython 3.10以上と、numpy/scipyが必要です。Python標準のtkinter GUIを使います。
2. `START_v141_GUI.cmd` を起動して、元のQGD ZIP（またはQGDフォルダー）を選びます。コマンドのみで操作する場合は `01_DECONVOLVE_QGD.cmd` です。
3. **神戸大学の40 QGDを処理する場合のみ**、個別の解析用パッケージに保存された `samples/kobe_fa_40_manifest_LOCAL.json` を測定一覧として選びます。GitHub公開用のソースZIPにはこの個別マニフェストを含めません。これにより29GC / 11EGA、TD/PY、ブランク、補正試料を正しく区別します。任意の他データでは、サンプル用の`manifest_example.csv`を元に測定一覧を作成してください。ファイル名だけで測定法を推定できない場合は安全のため停止します。
4. 新しい`nist_search/inputs/query_index.json`とMSPが作られたら `02_VERIFY_NIST_INPUTS.cmd` で全クエリの照合に合格することを確認します。
5. `03_CONFIGURE_NIST.cmd`でNIST MS Search 17（その他の適合版でも可）のパス、選択済みライブラリ、Automation設定を記録。NISTのOptions側でもAutomation有効・Number of hits to printが既定15以上であることを確認します。**設定画面への入力だけではNIST側の設定は変わりません。**
6. `04_RUN_ALL_NIST.cmd`で全GC、FA試料のみなら`05_RUN_FA_ONLY_NIST.cmd`で一括検索。NISTの画面とコンソールは閉じず、Windowsのスリープも無効にします。途中停止後の再開はNISTが完全に待機状態に戻ったことを確認して`06_RESUME_ALL_AFTER_IDLE.cmd`を使用します。
7. NIST検索完了後、`07_REBUILD_NIST_CSV_QC.cmd`から候補CSVとQC閲覧HTMLを再構成できます。出力は`nist_search/results/all/`、FA-onlyは`nist_search/results/fa/`です。`OPEN_QC_REVIEW*.html`が同定QC画面です。

**重要**：過去のv1.4.0、旧AMDIS型試験版、Global NNLS v0.3.1の検索結果は再利用できません。ピーク番号・スペクトルが変わるため、`nist_search/results`に残った旧チェックポイントと混ぜないでください。再計算する際はZIPを**別名の新しいフォルダーに再展開**してから開始してください。ソフトは既存のquery_index/結果がある場合、入力の自動上書きを拒否します。

## v1.4.1で変更した部分

- EIC（各m/zの抽出イオン信号）のピークを探索し、保持時間近傍のイオン形状から候補を形成。
- 全成分を1つの非負制約付き大域モデルでフィッティングし、同じ測定セル（スキャン×m/z）を複数の成分が重複して計上しないよう信号を配分。
- モデル間の強い重複・完全一致に近い成分の統合（類似する別ピークは自動統合しすぎない）。残差からの追加候補を探索後、共通モデルで再フィット。
- 面積配分チェック、過大予測、未説明信号、局所L2誤差、相対純度、EICピークS/Nなどを監査用に出力。
- NIST MSPは元QGDのSHA256、Run ID、保持時間、Scan、成分番号と対応付け、異なる入力を持つ既存検索結果の流用を拒否。
- 入力は**島津 GCMSsolution QGDの対応フォーマット**。EGAはTIC概要のみで、GC分離成分としてNISTには送信しません。

## 旧v1.4.0を引き継ぐ部分

- NIST MS Searchを操作するブリッジ本体：v1.4.0公開ソースを無変更で同梱。真正のNIST MS Searchプログラムおよびライブラリは各Windows PCで必要。
- 同定QC：`software/qc140.js`（classification model 2.2.0、QC rules 1.0.0）、ブラウザーによる候補一覧の検証。
- `09_OPEN_LEGACY_BROWSER_V140.cmd`は**旧v1.4.0のブラウザー処理**を開きます。ブラウザー画面のDeconvolutionボタンはv1.4.1 Global NNLSを実行しません。v1.4.1の解析は `START_v141_GUI.cmd` または `01_DECONVOLVE_QGD.cmd` から行ってください。
- 検索後のMF 800既定値は従来同様、同定QC閲覧画面から700に調整して探索的感度解析を行えます。ただし「700なら正しい分離」とはなりません。

## 解析値の解釈

`TotalIntensity`は非負モデルから観測イオン信号へ共有配分した応答の時間積分（近似的に counts×min）です。**校正済みのGCピーク面積でも含有濃度でもありません**。面積の保存検証は、全成分へ配分された信号の合計が観測信号以下であることの数値検証であり、分離正しさの証明ではありません。ベースラインの算定で分母となる信号量が変わるため、異なる補正法で求めた「カバー率」は直接比較できません。

`audit_v141/run_QA.csv`と`audit_v141/all_run_diagnostics.json`で、`accounted_fraction`、`model_overprediction_fraction`、`model_relative_l2`、`allocation_conservation_rel_error`を確認してください。過大予測と残差が大きい測定を、そのまま化学組成として使用しないでください。

## 完了済みの検証と限界

- 合成3成分（部分共溶出）でグローバルフィット・面積整合性テストが合格。
- 設定を意図的に2倍にした過大予測ケースでも、同一イオン信号の二重計上を防止できることを確認。
- 元の神戸大学ZIPの40 QGDを全て認識でき、個別解析用manifestにより29GC・11EGAを分類（公開ソースに実測ファイル・個別manifestは含みません）。
- 実QGDの2004年FA SS・TDとブランク計3測定の再処理を実行し、検索用1363 MSPの一意性と公式NISTブリッジ形式を検証。
- 真正NIST AMDISとの4測定の探索的比較は2026-10-22に実施。詳細は `docs/AMDIS_COMPARISON_2026-10-22_JA.md` を参照。
- Windows版NIST GUI上の一連の検索実行はパッケージ検証環境では未実施。包括的な分離精度評価および別装置・別メーカーの全条件テストも未完了です。

## GitHubへの更新

公開対象は `v1.4.1-rc1` のソース一式です。`docs/GITHUB_PUBLISH_ja.md`参照。既存のv1.4.0タグ・原稿の再現性を壊さないため、まず`feature/v1.4.1-global-nnls`ブランチへ追加し、レビュー後に`v1.4.1-rc1`プレリリースとしてください。NIST本体、ユーザーの実測QGD、ライブラリ、ローカルの検索結果、神戸大学のmanifestなどは**GitHubへアップしない**でください。

Project: https://github.com/Yasuro3/pygcms-pipeline

Copyright / licensing: PyGCMS Pipeline MIT license, repository contributors; the included upstream bridge/QC is identified by its v1.4.0 commit and hash manifest.


## リリースの識別

引用する版は **1.4.1-rc1**（2026-10-23）です。入力と検索結果の互換性を表す `software_version: "1.4.1"` は既存のデータ形式識別子です。再現性の記録には、これに加えてGitHubのリリースタグまたはコミットSHAを記載してください。今回の公開前検証は `pipeline_v141/docs/PUBLICATION_VALIDATION_v1.4.1-rc1.md` に記載しています。


## 分類表

`pipeline_v141/docs/CLASSIFICATION_REFERENCE_v141_JA.md` に A/OAr/C/N/F/S/R の定義があります。Fは脂肪酸のみではなく **Aliphatic / lipid-related** です。これらは探索的な報告用分類であり、分類エンジン2.2.0の新しい実装ではありません。
