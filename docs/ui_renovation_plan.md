# UI改造計画書

**最終更新**: 2026-03-25（PR-H2 は完了　次の公式着手対象は PR-I）

この文書は、`Fantasy_simulator` のユーザインタフェース（UI）を現状の簡素な CLI から、物語生成ゲームにふさわしい魅力的な体験へ進化させるための計画書である。前半では現状の問題と目標を整理し、後半では5つの専門領域（世界シミュレーション、運営型シム、インタラクティブ叙述、4X設計、ソフトウェアアーキテクチャ）の視点から提案された改善策をまとめる。最後に採用するライブラリや段階的な実行計画を提示する。

> **関連文書**: 本計画は `docs/implementation_plan.md`（公式な実装順・PR 分割・完了条件の正本）の `location_id` 移行・`WorldEventRecord` 導入・UI 連携規約、および `docs/next_version_plan.md` の `NarrativeContext` / `MapRenderInfo` 設計を前提としている。UI 改造の実装順や着手条件が他文書と衝突する場合は `docs/implementation_plan.md` を優先する。データモデルや migration の詳細はそれぞれの文書を参照のこと。
>
> **現時点の前提**: `docs/implementation_plan.md` 上では PR-0 から PR-H2 までが main に反映済みであり、
> region mapの意味化は導入済みである。次の公式着手対象は
> **PR-I** とする。本書もこの前提で読む。

---

## はじめに：現状の問題点

- 表現力が貧弱：現在の画面はログを流すだけで、キャラクターや場所の様子、冒険の展開を視覚的に伝えられない。イベントが大量に発生すると流れて見失う。
- 入力が単調：選択肢やコマンド入力が文字列ベースで、誤入力へのフォローや補完がない。物語の選択肢が増えた場合に煩雑になる。
- 視認性の問題：日本語と英語が混在する関係で文字幅が揃わないことがあり、AA や表の罫線が崩れる。
- 拡張性の乏しさ：UI 出力は `screens.py` / `ui_helpers.py` に集約されているが、表示ロジックがイベント処理と密接に連動しており、vNext で導入予定の月次進行やパーティ冒険、複数視点表示などを入れにくい。
- 盤面感の強さ：5×5 の地点グリッドは初期実装としては有効だったが、世界の広がりや大陸感、交通圏や地形障害の存在を感じにくい。
- メニュー制御の脆弱性は PR-D でキー分岐へ移行済みだが、今後 UI フレームワークを差し替えるなら
  atlas/region/detail の多段ナビゲーションも同じ抽象に乗せ続ける必要がある。

## 改造の目的

1. 物語を味わえる演出：重要人物や冒険の進行をハイライトし、背景となる世界の変化を地図やパネルで示す。
2. 選択と操作の快適さ：メニュー選択やテキスト入力を支援するインタラクティブな UI を導入し、ユーザの誤操作を減らす。
3. 多言語対応と横幅整合：日英併記や将来の多言語対応を見据えて、AA や表のレイアウトが崩れないよう調整する。
4. モジュール化：UI 層をドメインロジックから分離し、テストと保守を容易にする。将来的な TUI や GUI への移行を視野に入れる。
5. 観測体験の深化：地形、導線、危険偏在、world memory をまとめて読める観測 UI を成立させる。
6. 将来の worldgen 受け皿：ランダム大陸生成を将来導入できるよう、描画器と view model を固定 5×5 前提から外す。

## イベント表現と UI データ契約

- `WorldEventRecord` は世界側の正規イベント表現であり、保存・因果追跡・通知密度判定の基準とする。
- `EventRecord` は UI 表示・絞り込み・グルーピングに使う表示用レコードとして扱う。実装時は `WorldEventRecord` から導出する view model に限定するか、単一イベント型へ統一する。
- `World.event_records: List[WorldEventRecord]` を正規ストアとしつつ、`Simulator.history: List[EventResult]` と `World.event_log: List[str]` は互換層として残す。UI は adapter 経由でこの差を吸収し、新規の集計・表示ロジックは `WorldEventRecord` を参照する。
- 現行の 3 重イベントストアは段階的に整理する。`WorldEventRecord` を report / summary / event list / filter の唯一の入力源とし、`World.event_log` は表示派生物、`Simulator.history` は旧 save 互換 adapter へ縮退させる。
- 新規 UI 機能は `history` / `event_log` を直接参照しない。表示用 view model は正規データから都度生成する。

## 専門家別提案

### 専門領域A：世界シミュレーション設計
- 地理と履歴のビジュアライゼーション：場所が文字列だけで表現されているため、プレイヤーは世界の広がりを感じにくい。`location_id` 移行後は、街やダンジョンを ASCII マップとして表示し、各セルに最近起きた出来事や危険度を色分けする。場所ごとの発展度や事件履歴が UI に反映されることで、世界に記憶があると感じられるようになる。
- 冒険と世界進行の統合表示：冒険者の行動が世界に与える影響や、冒険失敗による疫病の広がりなどをレポートで示す。年次報告書だけでなく、冒険実行中にも世界の状態が変わることを地図上で更新し、プレイヤーが因果関係を理解できるようにする。

### 専門領域B：運営型シミュレーション設計
- ハイライトと編集：すべての出来事を同じ重さで表示すると体験が平板になる。重要人物や注目冒険を「スポットライト」として強調し、それ以外の出来事は年次ダイジェストにまとめる。プレイヤーは「注目キャラクター」「主要事件」「継続中の冒険」を切り替えて閲覧できるようにする。
- 通知密度の調節：内部シミュレーションは高密度でも、UI 上の通知を制御できるようにする。「高密度」「中密度」「低密度」のような設定を用意し、物語のテンポをコントロールする。設定に応じて表示するログをフィルタし、冒険体験をドラマチックに編集する。

### 専門領域C：インタラクティブ・ナラティブ設計
- 文章生成とテンプレート管理：現状のログは固定文章が多く、日本語・英語の管理が煩雑である。将来の LLM 導入を見据えつつ、Phase 1–4 ではテンプレートベースの文章生成モジュールを導入し、NarrativeContext を別レイヤで管理する。イベントに含まれる登場人物や場所に応じてテンプレートを選択し、ユーザに読みやすい文章を生成する。
- 多言語と表現の分離：Phase 1〜2 では現行 `i18n.py` の `_TEXT` / `_TERMS` と `tr()` / `tr_term()` を source of truth とし、その上でテンプレート選択層を重ねる。外部ファイル分離は互換 API を維持できる段階で行い、`wcwidth` を使って日本語と英語の混在時の横幅を正確に計算し、テーブルやマップが崩れないようにする。

### 専門領域D：戦略ゲームUX設計
- 時間粒度とレポート設計：月次化や週次化はシミュレーション密度を上げるが、UI で処理できる単位を先に定める必要がある。月次進行を導入する際は、「1か月の出来事ダイジェスト」をカード形式で表示し、プレイヤーが興味を持った部分を選んで詳細を見るようなインタラクションを用意する。レポートは「人物別」「場所別」「冒険別」に分け、何が変わったかを明確に示す。
- 因果関係の可視化：疫病の流行がその後の経済に与えた影響や、冒険の失敗が他の冒険者の士気を下げたことなどを、シンプルなグラフやアイコンの変化で表現する。これによりプレイヤーがシミュレーションの因果を掴めるようにする。

### 専門領域E：ソフトウェア設計・アーキテクチャ
- 責務分離と層構造：現行コードは UI 出力が `screens.py` / `ui_helpers.py` に集約されている一方、`world.py` の `render_map()` や `simulator.py` の `get_summary()` / `get_character_story()` など文字列生成 API も散在している。イベントをデータ構造（`EventRecord` / `WorldEventRecord`）として定義し、renderer / presenter 層に表示判断を集約することで、新しい TUI フレームワークへの移行や GUI 版への拡張を容易にする。
- モジュール分割とテスト容易性：UI ロジックは `ui/` パッケージに分離し、レンダリング関数を純粋関数に近づける。将来 Textual などのフレームワークを導入する際も、UI 層の交換をスムーズに行える。

## 採用するライブラリ・技術

### 本体 UI 基盤の短期第一候補
- **Rich**：パネル、テーブル、色付きログなどの表示基盤。現行の ANSI エスケープ手動管理（`ui_helpers.py` の `_c()` 関数）を置き換える候補。Rich は内部で CJK 文字幅計算を持つ（`rich.cells`）ため、Rich 経由の出力では別途 `wcwidth` は不要。PR-H2 の最小導入で CJK 幅・既存 renderer との責務分担・snapshot テスト安定性を検証し、問題がなければ採用を確定する。
- **wcwidth**：Rich を経由しない独自レンダリング（ASCII / AA マップ）で日本語・英語混在時の文字幅を正しく計算するために使用する。Rich 経由の出力には不要。
- **prompt_toolkit**：インタラクティブな入力補完・選択 UI。直接 `input()` を置換せず、入力抽象の背後に隔離する。将来 Textual を採用する場合は置換前提とする。

### PR-G の PoC で検討（候補）
- **FastNoiseLite**：terrain generation の seed 固定実験、height / moisture / temperature 分布生成、ASCII preview の元データ生成に向く。worldgen PoC の第一候補。
- **WorldEngine**：プレート、降雨、侵食を含む外部生成 world の比較や、自前地形生成との参照比較に向く。本体依存ではなく比較・参照向け。
- **Azgaar’s Fantasy Map Generator**：海岸線や国家スケールの広がり比較、世界観試作の支援ツール。本体依存対象ではなく設計支援向け。
- **python-tcod**：地点詳細図、ダンジョン入口、局所 map の生成補助向け。continent 表現の主軸ではなく、局所詳細用候補。

### Phase 3 以降で検討（候補）
- **Textual**：本格 TUI の第一候補。Rich 上に構築され、非同期・マウス対応・高度なレイアウトを備える。prompt_toolkit とは入力モデルが異なるため、採用時は全面置換を前提とする。
- **演出（Rich Animation）**：重要イベントやオープニングの軽い演出は、Rich の `Live` / `Status` / `Progress` などの既存機能で対応可能か先に評価する。別途ライブラリを追加するのは Rich で不足する場合に限る。

## PR-G 拡張方針：可変ワールド対応・地形表現・worldgen PoC

### この追記の目的

現状の UI 計画では、ASCII マップやレポートの導入方針はあるが、まだ「5×5 地点盤面を前提とした見た目強化」に読める余地がある。  
しかし本作が本来目指しているのは、**土地の広がり・導線・危険偏在・噂の熱・記念碑や死地の履歴が読める観測 UI** である。

そのため UI 側では、次の判断を明確に固定する。

1. **AA は装飾ではなく、世界状態の可視化である**
2. **1 マス 1 地点の盤面感を残したままでは没入感に限界がある**
3. **地形そのものを表現し、site はその上に重ねる**
4. **将来的なランダム大陸生成を見据え、描画器は固定 5×5 前提を捨てる**
5. **PoC を許容するが、本体統合用 API と実験用スクリプトは分ける**

## 追加する UI 設計原則

### 原則 1: 地形と地点を別レイヤとして描く
今後の map renderer は、次の二層を前提に設計する。

- **terrain layer**
  - 海、海岸、平野、森林、丘陵、山脈、川、湿地、荒野など
- **site / route overlay layer**
  - 都市、村、港、砦、遺跡、ダンジョン入口、街道、峠道、海路、季節道など

### 原則 2: 地図は三層表示を維持するが、内部情報量は増やす

1. **ワールド全体図**
2. **地域図**
3. **地点詳細図**

#### ワールド全体図
- 海岸線
- 山脈
- 森林帯
- 平野
- 主要 site
- 主要 route
- `danger_band`
- `traffic_band`
- `rumor_heat_band`
- `has_memorial` / `has_alias` / `recent_death_site`

#### 地域図
- 周辺導線
- 峠
- 河川
- 門
- 市場
- 掲示板
- 墓碑
- 事故地点
- 封鎖道 / 崩落道
- 先行パーティの痕跡

#### 地点詳細図
- 都市 / 遺跡 / 野外 / ダンジョン入口などの局所 AA / 準AA
- 最近の痕跡
- world memory
- 現在状態の短い要約
- その場所で今読むべき情報への導線

### 原則 3: 「綺麗」より「判断できる」を優先する
優先順位は次の通りとする。

1. いまどこが危険か分かる
2. どこに噂が集中しているか分かる
3. どこに過去の傷跡や記念が残っているか分かる
4. どこへ注目すべきか分かる
5. そのうえで、雰囲気がある

### 原則 4: 狭幅端末では必ず簡易表示へ落ちる
map renderer は最低でも次のモードを持つ。

- **full**
  - 広い端末向け。全体図の詳細版
- **compact**
  - 一部情報を省略した簡易版
- **minimal**
  - site / route / marker のみを見る最小版

### 原則 5: PoC の実験描画と本体 UI を分離する
- `fantasy_simulator/ui/`
  - 本体で使用する renderer / presenter
- `tools/worldgen_poc/`
  - 生成結果の ASCII preview / デバッグ出力 / 比較可視化

## 追加する map renderer の責務

### 新たに担う責務
- terrain のベース glyph 決定
- route の overlay glyph 決定
- world memory の marker 付与
- site importance に応じたラベル簡略化
- 表示幅に応じた簡易化
- world-scale / region-scale / site-detail の view model 切替

### 逆に担わない責務
- game logic の判定
- state 値そのものの計算
- site 配置ルールの決定
- 噂や危険度の更新

## worldgen PoC を前提にした UI 側の受け皿

- 可変 world width / height
- site が terrain 座標上に載る構造
- 海岸線・山脈・河川の長い連続表現
- seed 固定 terrain の preview 表示
- generated world を既存 UI で開ける導線

### UI 側で必要な view model 例
- `TerrainCellRenderInfo`
- `SiteRenderInfo`
- `RouteRenderInfo`
- `WorldMapRenderInfo`
- `RegionMapRenderInfo`
- `SiteDetailRenderInfo`

現行の `MapRenderInfo` / `MapCellInfo` はその土台としつつ、terrain layer を表現できるよう拡張する。

## 段階的な UI 改造計画

### Phase 0：基礎整備（PR-1〜PR-D 完了）
- [x] `screens.py` / `ui_helpers.py` の責務を棚卸しし、`ui/` パッケージを作成する
- [x] `screens.py` の `_show_results()` 等で `action == tr("...")` による分岐をキーベースの選択に変更し、ロケール依存の制御フローを解消する
- [x] `InputBackend` と `RenderBackend` を導入する
- [x] `screens.py` / `main.py` / `character_creator.py` の全 I/O を backend 経由に移行する
- [x] presenter / view-model の最小層を導入する（`ui/presenters.py`, `ui/view_models.py`）
- [x] 月報カードなど一部表示を `WorldEventRecord` 起点の view model へ切り替える
- [ ] `wcwidth` による幅計算ユーティリティを整理する

### Phase 1：薄いリッチ化　
> 注: PR-H1 完了により region map の意味論強化は先行完了、以後この Phase では固定レイアウト / 見出し / 余白 / 強調 / 操作導線の整理を主対象とする
- [ ] Rich を導入し、観測画面のレイアウト、見出し、余白、強調を整理する
- [ ] タイトルや章見出しに Rich の `Panel` / `Text` / `Rule` を用いた軽量装飾を適用する
- [ ] prompt_toolkit によりメニュー選択やコマンド入力を段階的に改善する

### Phase 2：PR-G（可変ワールド対応・地形表現・観測 UI 初版）
> 注: region map の読解性強化は後続の PR-H1 で補強済み
- [x] `terrain + site overlay` を扱える world-scale map renderer を導入する
- [x] ワールド全体図で海岸線、山脈、森林帯、平野、主要 route、world memory を表示できるようにする
- [ ] 地域図で導線、峠、河川、門、市場、掲示板、墓碑、事故地点、封鎖道、痕跡を判断可能な形で読めるようにする
  - [x]  PR-G2 で region 基盤は導入済み
  - [x]  PR-H1 で summary / closure / danger / rumor / world memory の読解性を強化済み
  - [ ]  門 / 市場 / 掲示板 / 河川などの richer local semantics の拡張
- [x] 地点詳細図で局所 AA / 準AA と最近の痕跡を接続する
- [x] world サイズが固定 5×5 でなくても描画できるようにする
- [x] `wide` / `compact` / `minimal` 表示モードを導入する
- [x] `WorldEventRecord` から月報カード用 view model を生成する
- [ ] 年次・月次レポートをカード形式で全面統一する

### Phase 2.5：worldgen PoC 表示支援
- [ ] seed 固定 terrain preview を ASCII で出力できるようにする
- [ ] generated world を既存 UI 上で開ける簡易導線を追加する
- [ ] terrain preview と site overlay の比較表示を試せるようにする

### Phase 3：TUI への拡張
- [ ] 可変サイズ world のスクロール / ズーム / フォーカス制御が必要か評価する
- [ ] world-scale map と region-scale map を同時表示する複数ペイン構成が必要か評価する
- [ ] generated world preview を TUI 上で扱う要件があるか評価する
- [ ] 上記いずれかが必要と判断された場合、Textual を採用候補として検証・導入する

### Phase 4：演出の追加
- [ ] Rich の `Live` / `Status` / `Progress` で対応可能な演出範囲を評価する
- [ ] Rich で不足する場合に限り、追加ライブラリを検討する
- [ ] 情報の可視化を邪魔しない範囲で、物語的な盛り上がりを補助する演出を追加する

## テスト戦略

- [x] 既存の `test_screens.py`, `test_ui_helpers.py` を移行中も維持し、旧 entry point と helper の互換性を確認する
- [x] `test_ui_integration.py` で `RecordingRenderBackend` / `ScriptedInputBackend` を用いた統合テストを追加し、UI 基盤が差し替え可能であることを証明する（ゼロ stdout 漏洩テスト含む）
- [x] 可変サイズ world map の描画テストを追加する
- [x] terrain + site overlay の観測 UI テストを追加する
- [x] `has_memorial` / `has_alias` / `recent_death_site` フラグが地図に反映されることを確認する
- [x] region map の summary / closure / danger / rumor / world memory の focused テストを追加する
- [x] region / atlas の一部画面について snapshot-style テストを追加する
- [x] `compact` / `minimal` 表示について EN / JA の表示幅 budget 検証を追加する
- [ ] 日本語英語混在時のセンタリング、表幅、AA 罫線が崩れないことを確認する包括的な幅崩れテストを拡張する
- [ ] メインメニュー、ワールドマップ、月報、キャラクター一覧など主要画面全体の文字出力スナップショット比較テストを追加する
- [ ] `WorldEventRecord` から期待するパネル・レポート・通知カードが生成されることを確認するイベント表示テストを追加する
- [x] 端末幅に応じて `compact` / `minimal` 表示へ自動的に切り替える統合テストを追加する（PR-H2）
- [ ] seed 固定 terrain preview / worldgen PoC の再現性テストは PR-G3 以降で追加する

## 結論

短期的には **Rich + prompt_toolkit + wcwidth** の組み合わせが最も実用的で、既存 CLI を大きく壊さずに観測体験を改善できる。ただし順序は Rich 先行ではなく、**region map の意味論強化を主線、薄い Rich 化を補助線** とする。
region map の意味論強化は PR-H1 で完了
次段では PR-H2 として、薄い Rich 化を本線として進める
prompt_toolkit と将来の Textual は根本的に異なる入力モデルであるため、prompt_toolkit 依存コードは入力抽象の背後に隔離する。

そのうえで、次段階の map UI は「5×5 地点盤面の豪華化」ではなく、**terrain を持つ world の上に site と route が重なり、さらに world memory が履歴として染み出す観測 UI** として設計する。  
main の現状では、このうち PR-G1 / PR-G2 に相当する基盤はすでに導入済みである。以後の UI 課題は、
その表示器を worldgen PoC・より厚い report UI・将来の TUI 基盤へどう接続するかに移っている。

AA はそのための手段であり、目的ではない。
