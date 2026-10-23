# PyGCMS Pipeline v1.4.1-rc2 — 公開用mzML専用版

**公開版の入力はXML形式のmzMLのみです。** 島津GCMSsolutionのQGDを直接開く機能は、本バージョンの解析用GUIおよびコマンドから取り除きました。QGDを扱う研究室内版は別に保管してください。

## 操作方法（Windows）

1. GitHubのソースZIPを展開し、`pipeline_v141`フォルダーを開きます。
2. `00_INSTALL_DEPENDENCIES.cmd`を初回実行します（Python 3.10以上、NumPy/SciPy）。
3. `START_v141_GUI.cmd`をダブルクリックします。
4. XML `.mzML`ファイル、mzMLファイル群を含むフォルダー、またはmzMLを収納したZIPを選択します。
5. 測定法を`PY`、`TD`、`SS`、`EGA`、`GC_BLANK`から選びます。複数ランの詳細設定にはSHA256に対応したmanifestを指定します。
6. **1. mzML内容確認**で入力確認し、**2. 全mzMLを再分離**でGlobal NNLSを実行します。
7. 必要なら`02_VERIFY_NIST_INPUTS.cmd`で検索対象の整合性を確認し、ライセンスを持つNIST MS Searchへ渡します。NISTライブラリは同梱しません。

コマンドライン使用例：

```bat
py -3 engine\batch_v141.py --input "C:\\data\\test_PY.mzML" --phase PY --output nist_search
```

## 対応範囲

- XML mzML、MS1、m/z–intensityの32/64-bit float配列、非圧縮・zlib圧縮に対応。
- 走査時刻を分に統一し、m/z 35–550を名目質量に集約します。
- MS-Numpressや非対応の圧縮方式は明示的にエラーにします。
- 生のQGD等、メーカー独自形式は解析入力として受け付けません。
- EGAはTIC要約のみで、GC分離成分としてNIST検索しません。
- 入力を上書きせず、別の解析結果を同一NIST結果ディレクトリに混ぜない設計です。

## 検証状況・注意

Global NNLSは開発中の**試験版**です。合成波形による数値検証とMSP/NISTクエリ照合の従来テストがありますが、**本mzML専用変更後のWindows実測データによるend-to-end実行は未確認**です。MS1のデコンボリューションで得たスペクトルが化学種の正しい同定を意味するわけではありません。応答の時間積分は濃度やGCMSsolution校正ピーク面積ではありません。

従来の`v1.4.1-rc1`タグは研究再現性のためそのまま残しています。Git履歴から過去のQGDコードを消去したわけではありません。過去のv1.4.0のNIST/QC関連アーカイブは版を固定した比較用の資産であり、v1.4.1-rc2のmzML解析エントリポイントではありません。

詳細：`MZML_ONLY_RELEASE.md`。
