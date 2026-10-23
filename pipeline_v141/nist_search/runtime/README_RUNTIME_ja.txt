神戸大学データ用 PyGCMS Pipeline 1.4.0 最小実行ファイル

正式タグ v1.4.0 / commit 7d7ab77cef342cf5061eb87c412126789f152a3f から、必要なファイルを内容無改変で同梱しました。UPSTREAM_MANIFEST.json に上流 URL、Git blob SHA、SHA-256 を記録しています。この説明と manifest は配布用に追加した文書です。

通常は上位フォルダーの今回用ランチャー／バッチ手順を使用します。この runtime 単独では、実際の NIST MS Search 実行ファイルを指定して scripts/nist_mssearch_bridge_server.py を Python 3.10 以降で起動できます。ファイル連携 backend=file に必要な Python モジュールは標準ライブラリです。nist_dll_backend.py は公式の任意 DLL backend 用ファイルで、今回のファイル連携では追加パッケージの導入は不要です。

NIST MS Search 本体とライセンス付きライブラリは含まれていません。実際のインストール場所、利用ライブラリ、Automation の設定、Number of hits to print はユーザー PC で確認してください。並列の検索要求は送らず、検索は順番に実行してください。

software/index.html は公式の自己完結アプリです。QC140 エンジンと UI は HTML 内に埋め込まれており、併置した qc140.js／qc140_ui.js は正規ソースの確認用です。bridge の /app も同じ HTML を返します。相対ディレクトリ構成を維持してください。

README.md と docs/ は上流の原文です。README.md には完全配布版にだけ含まれるファイルへの言及があります。この最小版にはサンプルデータ、上流 Windows .cmd ランチャー、上流の過去実行用 NIST 設定は含めていません。provenance/nist_configuration_template.yaml は記録用ひな形であり、今回の実測設定ではありません。

旧 v1.4.0 ブラウザー処理の TotalIntensity については、信号倍率が二重に掛かる挙動が確認されています。この説明は runtime 内の従来ブラウザー処理に適用されます。

v1.4.1 の Global NNLS パイプラインが出力する TotalIntensity は別の指標で、各 scan×m/z のベースライン補正後の観測信号を各成分に重複なく配分した時間積分（近似的に counts×min）です。QC の response、response%、群比は、この入力値から再集計されます。旧 v1.4.0 の値とは直接比較できません。これらを濃度、校正済みピーク面積、mg 当たり直線応答、質量割合と解釈しないでください。候補名・分類は暫定的なライブラリ照合結果であり、標準物質による確定同定を意味しません。
