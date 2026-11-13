# StudyPlan AI

社内の待機メンバー向けの学習計画サポート Web アプリ（MVP）。
「○○を学習したい」（IT技術全般）と現状スキル・目標レベル・期間・1日の学習時間を入力すると、
**AI が教材（公式ドキュメント・記事・動画など）を探し、参考時間を読み取って、学ぶ順番・時間配分・日別スケジュールまで作ります。**
プログラムは AI の結果に間違いがないか（日付・1日の時間・合計・教材の抜け漏れ）を確認し、問題があれば AI に作り直しを依頼します。

企画・要件は Notion、画面案は Figma（UI案 v0.2）で管理しています。

## 画面

| 画面 | パス | 内容 |
|---|---|---|
| S01 ログイン | `/login` | MVP は簡易ログイン（ユーザーを選ぶ）。本番は社内 SSO |
| S02 ダッシュボード | `/` | 今日のタスク、達成率、遅れのお知らせ、マイプラン |
| S03 プラン作成 | `/plans/new` | 単元の入力（候補表示）、レベル（単元別の目安）、期間、学習できる時間 |
| S05 プラン提案 | `/plans/{id}/proposal` | 教材カード（参考時間と根拠・取得元）、AI が決めた配分、AI の判断、チェック済み表示、週カレンダー |
| S06 進捗・リスケ | `/plans/{id}` | タスクの完了・実績・メモ、計画と実績のグラフ、AI のリスケ案 |
| S07 育成担当ビュー | `/mentor` | メンバーの進捗、レビュー待ち件数 |
| S08 AI提案レビュー | `/review` | AI が探した教材の確認・承認（カタログに登録）、API の無料枠の利用状況 |

## 構成

```
backend/   FastAPI + SQLAlchemy 2 + Pydantic v2（Python 3.12+）
  app/ai/        AI の共通インターフェース・デモ AI・Gemini（AI_PROVIDER で切替）
  app/search/    無料検索 API（Tavily・Qiita・YouTube・デモ）と切替（上限に達したら次へ）
  app/services/  単元の正規化 / 教材選定 / 参考時間の読み取り / スケジュール作成と確認 / リスケ
  data/catalog.json  初期の教材カタログ（Python・AWS（EC2・VPC）・SQL）
frontend/  Next.js 15（App Router, TypeScript, Tailwind CSS）
```

処理の流れ（Notion 02_処理概要）：

1. 単元の正規化：別名の辞書（例：パイソン → Python）→ なければ AI。範囲が広すぎる単元（例：AWS）は候補を出して絞り込んでもらう
2. 教材選定：教材カタログ → なければ無料検索 API で候補を集め、AI がレベルに合うものを選ぶ（「AI提案（未レビュー）」として保存）
3. スケジュール作成：AI が参考時間・順番・配分・日別の予定を作る → `validator.py` で確認 → NG なら問題点を伝えて作り直し（最大2回）
4. リスケ：未完了のタスクを AI が残りの学習できる日に組み直す → 同じ確認

## 起動方法（ローカル）

### バックエンド

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

起動時にテーブル作成と初期データ投入を行います（DB は既定で `backend/studyplan.db` の SQLite）。
API ドキュメント：http://localhost:8000/docs

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

http://localhost:3000 を開き、ログイン画面でユーザーを選びます（山田・鈴木＝メンバー、佐藤＝育成担当、管理者）。

### Docker Compose（PostgreSQL を含む一式）

```bash
docker compose up --build
```

## AI・検索の設定（API キー）

キーがなくても **デモ AI・デモ検索** で一通り動きます（外部には通信しません。デモ検索の URL は example.com のダミーです）。
`.env.example` を `.env` にコピーし、キーを入れると本物に切り替わります。

| 設定 | 内容 |
|---|---|
| `AI_PROVIDER=gemini` ＋ `GEMINI_API_KEY` | Gemini API（無料枠を想定）。1日の上限は `GEMINI_DAILY_LIMIT` |
| `SEARCH_PROVIDERS=tavily,qiita,youtube` | 検索 API を優先順に。各キーは `TAVILY_API_KEY`・`QIITA_TOKEN`（任意）・`YOUTUBE_API_KEY` |
| `URL_CHECK=true` | 教材 URL の実在チェックを行う |
| `ALLOWED_DOMAINS` | 検索してよいドメイン（公式ドキュメント系） |
| `TODAY` | デモ用に「今日」を固定（例：`2026-12-10`） |

注意：

- **Gemini の無料枠では、送った内容が Google の製品改善に使われます。** アプリが AI に送るのは単元名・レベル・目的・日付・教材情報だけで、氏名などは送りません（`ScheduleContext` に個人情報の項目がないことをテストで確認しています）。社内の生成 AI 利用ルールの確認が必要です
- 無料枠の回数は `api_usage` テーブルに記録し、S08 で確認できます。上限に達した検索 API は飛ばして次を使います
- 実際の Gemini・Tavily・Qiita・YouTube への接続は未確認です（キー未取得のため）。各アダプタは通信をモックしたテストで確認しています

## テスト

```bash
cd backend && .venv/bin/pytest -q          # 65件：確認ロジック、カレンダー、AI の作り直し、API の一連の流れ、外部 API アダプタ
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

## MVP の範囲外（次の段階）

- S04 スキル診断、社内 SSO、通知（Slack・メール）、カレンダー出力（.ics）、CSV/PDF 出力
- Claude API のアダプタ（予算がついた場合）、Alembic によるマイグレーション、本番デプロイ
- 教材カタログの管理画面（現在は `data/catalog.json` と S08 の承認で登録）
- リスケで期間内に収まらなかったタスクは、適用するとプランから外れます（後回しの一覧として残す改善が必要）
- デモ AI は決まった手順で結果を作るもので、教材の中身を理解して判断しているわけではありません
