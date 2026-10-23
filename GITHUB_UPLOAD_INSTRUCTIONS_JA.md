# GitHub更新用：PyGCMS Pipeline v1.4.1 RC（2026-10-22の分類表追補）

## 登録方法

1. `https://github.com/Yasuro3/pygcms-pipeline` をCloneし、現行main/default branchから新しい `feature/v1.4.1-global-nnls` ブランチを切ります（既存同名ブランチがある場合はそのブランチへ追加）。
2. このZIPを展開し、**`pipeline_v141/` と `docs/` の構造のまま**リポジトリ直下へコピーします。既存 `v1.4.0` タグは変更しないでください。
3. 上記の新規文書 `pipeline_v141/docs/CLASSIFICATION_REFERENCE_v141_JA.md` と `.../AMDIS_COMPARISON_2026-10-22_JA.md`、README、CITATION.cff等を新ブランチにコミットします。
4. `python pipeline_v141/engine/test_global.py` および `python pipeline_v141/engine/test_nist_contract.py` を実行します。
5. Pull Requestでコードと注意書きを確認し、`v1.4.1-rc1` を *Pre-release* として公開します。正式版v1.4.1の安定版タグは独立検証後にしてください。

**ZIPファイルをGitHubのソースコードとしてそのまま1ファイル登録しないでください。** 展開後のファイル/フォルダをGit管理します。この文書は公開用ソースの構成と、履歴を保持する公開手順を示します。公開対象の識別子は `v1.4.1-rc1` です。

## 重要な制限

- v1.4.1 Global NNLSは実験実装。過大予測が残り、完全な化学的分離が検証されたものではありません。
- `pipeline_v141/nist_search/runtime/software/index.html` は従来版ブラウザー処理であり、新しいGlobal NNLS実行画面ではありません。`pipeline_v141/START_v141_GUI.cmd` を使用してください。
- 分類コード `A/OAr/C/N/F/S/R` の説明は研究結果向け資料であり、分類エンジンを変更するパッチではありません。
- 測定生QGD、MSP、NIST検索結果、NIST実行ファイル・ライブラリ、個人PCパス、個人データをGitHubへ入れないでください。
- 過去版のタグと対応論文の再現性を保持してください。

## GitHub公開後の引用

使用したrelease tagまたはcommit SHAとSoftwareX論文を引用します。ソフト本体へのZenodo DOIは今回付与しません。研究データDOIは別途取得してください。
