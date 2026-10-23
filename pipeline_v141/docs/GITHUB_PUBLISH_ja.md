# PyGCMS Pipeline v1.4.1 のGitHub公開手順

**推奨は「開発ブランチ → Pull Request → プレリリース」です。** v1.4.0は修正せずに残します。タグv1.4.0を動かしてはいけません。

## GitHub Desktopを使う場合

1. GitHub Desktopで `Yasuro3/pygcms-pipeline` をCloneし、既存の最新default branchから `feature/v1.4.1-global-nnls` ブランチを作成。
2. GitHub公開用ソースZIPを展開し、中の `pipeline_v141` フォルダーを**リポジトリ直下**に置きます。同梱した `README_v1.4.1_JA.md` 等も、zip記載のフォルダー構造のまま追加してください。
3. ソースのみをコミット。**raw QGD、MSP、NIST検索結果、NISTソフト・ライブラリ、神戸大学manifest、個人PCパス**はコミットしません。
4. GitHub DesktopでPublish branchし、GitHubからPull Requestを作成。
5. 自動テストが通り、独立AMDIS比較などの限界をREADMEに明記できたら、`v1.4.1-rc1`をPre-releaseとして公開。問題が解消されるまでは**安定版v1.4.1の正式タグ**を作成しません。

## Gitコマンドの場合

```powershell
git clone https://github.com/Yasuro3/pygcms-pipeline.git
cd pygcms-pipeline
git switch -c feature/v1.4.1-global-nnls
# Source ZIP 内の pipeline_v141/ と docs/ をこのリポジトリ内に展開
git add pipeline_v141 docs/CHANGELOG_v1.4.1.md
git commit -m "Add experimental globally coupled NNLS deconvolution (v1.4.1 RC)"
git push -u origin feature/v1.4.1-global-nnls
```

次にGitHub上で `main` / `feature/v1.4.1-global-nnls` のPRを確認してください。

## 論文の再現性

v1.4.0とv1.4.1ではデコンボリューションが異なり、成分表・ピーク番号・相対応答は互換ではありません。採用した原稿には必ず「ソフト版・コードコミット・設定JSONのSHA256・入力ファイルのSHA256・NISTバージョン/ライブラリ版」を記録します。v1.4.1のソフト本体にはZenodo DOIを付与しないという現在の方針なら、GitHubのタグ/コミットを直接引用できます。研究データのDOIは別に取得してください。
