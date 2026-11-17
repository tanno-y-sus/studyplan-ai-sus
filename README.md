# StudyPlan AI

社内の待機メンバー向けの学習計画サポート Web アプリ（MVP）。
「○○を学習したい」（IT技術全般）と現状スキル・目標レベル・期間・1日の学習時間を入力すると、
**AI が教材（公式ドキュメント・記事・動画など）を探し、参考時間を読み取って、学ぶ順番・時間配分・日別スケジュールまで作ります。**
プログラムは AI の結果に間違いがないか（日付・1日の時間・合計・教材の抜け漏れ）を確認し、問題があれば AI に作り直しを依頼します。

企画・要件は Notion、画面案は Figma（UI案 v0.2）で管理しています。

## 画面

| 画面 | パス | 内容 |
|---|---|---|
| S01 ログイン | `/login` | メールアドレスとパスワード |
| 新規登録 | `/register` | 氏名・メール・パスワード。最初の登録者が管理者 |
| アカウント設定 | `/settings` | パスワードの変更 |
| ユーザー管理 | `/admin/users` | 管理者のみ。権限の変更（メンバー・育成担当・管理者）、仮パスワードの発行 |
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
  app/api/auth.py  新規登録・ログイン・ユーザー管理
frontend/  Next.js 15（App Router, TypeScript, Tailwind CSS）
```

処理の流れ（Notion 02_処理概要）：

1. 単元の正規化：別名の辞書（例：パイソン → Python）→ なければ AI。範囲が広すぎる単元（例：AWS）は候補を出して絞り込んでもらう
2. 教材選定：教材カタログ（育成担当が承認した教材）→ なければ無料検索 API で候補を集め、AI がレベルに合うものを選ぶ（「AI提案（未レビュー）」として保存）
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

起動時にテーブルを作成します（DB は既定で `backend/studyplan.db` の SQLite）。初期データ（ユーザー・教材）は入りません。

**以前の版（仮のメンバーを選んでログインする版）の `studyplan.db` は使えません。** 起動時に案内が出たら、サーバーを止めて `backend/studyplan.db` を削除し、起動し直してください（データは消えます）。
API ドキュメント：http://localhost:8000/docs

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

http://localhost:3000 を開き、「新規登録」でアカウントを作ります。

- **最初に登録した人が管理者**になります。以降に登録した人はメンバーです
- 管理者は「ユーザー管理」で、育成担当・管理者に変更できます（最後の管理者は外せません）
- パスワードを忘れた人には、管理者が「仮パスワードを発行」します。本人はログイン後に「アカウント設定」で変更します

### ログインの設定（`.env`）

| 設定 | 内容 |
|---|---|
| `ALLOWED_EMAIL_DOMAINS` | 新規登録できるメールのドメイン（例：`example.co.jp`。カンマ区切り。空なら制限なし） |
| `SESSION_DAYS` | ログインしたままにする日数（既定 14） |
| `COOKIE_SECURE` | https で公開するときは `true` |

パスワードは scrypt で変換した値だけを保存します。ログイン状態は HttpOnly の Cookie で、同じメールアドレスで15分に10回失敗すると一時的にログインできなくなります。

画面からの `/api/*` は、フロントエンドのサーバーがバックエンドに中継します（`next.config.ts` の rewrites）。
ブラウザは画面と同じ URL だけにアクセスするので、クラウドのプレビューや社内サーバーでもポート 3000 を開ければ動きます。
中継先は環境変数 `BACKEND_URL`（既定 `http://localhost:8000`。ビルド時に埋め込まれる）で変更できます。

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

### Gemini を使う手順

1. [Google AI Studio](https://aistudio.google.com/) に Google アカウントでログインし、「Get API key」→「Create API key」でキーを発行する（無料枠は支払い情報の登録不要）
2. リポジトリ直下（または `backend/`）の `.env.example` をコピーして `.env` にし、次を書く

   ```bash
   AI_PROVIDER=gemini
   GEMINI_API_KEY=（発行したキー）
   ```

3. 接続を確認する（キーとモデル名の確認 → 小さな質問を1回送る）

   ```bash
   cd backend
   .venv/bin/python -m app.ai.check        # Windows は .venv\Scripts\python -m app.ai.check
   ```

   「準備完了です」と出れば OK。モデルが見つからない場合は、使えるモデル名の一覧が出るので `GEMINI_MODEL` に設定する
4. バックエンドを起動（または再起動）する。起動ログと S03・S08 の「使用中の AI」に Gemini と表示される

Gemini を使えないとき（キーの誤り・無料枠の上限・通信できない・Gemini 側の障害）は、デモ AI に切り替えずに **エラーで止めます**（画面に理由を表示、プランは保存しない、作り直しで回数を無駄にしない）。
`.env` はバックエンド起動時に読み込みます（すでにある環境変数が優先）。テストでは読み込みません。

### 本物の教材（実在する URL）を探す手順

既定の `SEARCH_PROVIDERS=demo` では、教材は example.com のダミー（実在しない）です。AI が Gemini でも、候補がダミーなので結果もダミーになります。

| 検索 | 探すもの | キー |
|---|---|---|
| `qiita` | 日本語の記事 | 不要（あれば `QIITA_TOKEN`。1時間あたりの回数が増える） |
| `tavily` | 公式ドキュメント（`ALLOWED_DOMAINS` のサイトだけ） | `TAVILY_API_KEY`：https://app.tavily.com でサインアップすると発行（無料・月1,000回） |
| `youtube` | 動画（長さから学習時間を計算） | `YOUTUBE_API_KEY`：Google Cloud コンソールで「YouTube Data API v3」を有効にして「認証情報 → API キー」（無料・1日1万ユニット、検索1回100ユニット） |

```bash
SEARCH_PROVIDERS=tavily,qiita,youtube
TAVILY_API_KEY=（発行したキー）
YOUTUBE_API_KEY=（発行したキー）
```

キーがない検索は飛ばします（まずは `SEARCH_PROVIDERS=qiita` だけでも本物の記事になります）。
使用中の検索は起動ログと S03・S08 に表示されます。
本物の検索に切り替えると、以前デモ検索で見つけた教材は使い回さずに「却下」扱いにして、検索し直します（作成済みのプランはそのまま）。

注意：

- **Gemini の無料枠では、送った内容が Google の製品改善に使われます。** アプリが AI に送るのは単元名・レベル・目的・日付・教材情報だけで、氏名などは送りません（`ScheduleContext` に個人情報の項目がないことをテストで確認しています）。社内の生成 AI 利用ルールの確認が必要です
- 無料枠の回数は `api_usage` テーブルに記録し、S08 で確認できます。上限に達した検索 API は飛ばして次を使います
- 実際の Gemini・Tavily・Qiita・YouTube での動作（正しいキーでの回答）は未確認です（キー未取得のため）。各アダプタは通信をモックしたテストで確認しています。Gemini はキーが誤っている場合のエラー表示まで本物の API で確認済み

## テスト

```bash
cd backend && .venv/bin/pytest -q          # 108件：確認ロジック、カレンダー、AI の作り直し、API の一連の流れ、外部 API アダプタ、Gemini 連携、新規登録・ログイン
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

## MVP の範囲外（次の段階）

- S04 スキル診断、社内 SSO、通知（Slack・メール）、カレンダー出力（.ics）、CSV/PDF 出力
- Claude API のアダプタ（予算がついた場合）、Alembic によるマイグレーション、本番デプロイ
- 教材カタログの管理画面（現在は S08 の承認で登録）
- メールでのパスワード再設定（現在は管理者が仮パスワードを発行）
- リスケで期間内に収まらなかったタスクは、適用するとプランから外れます（後回しの一覧として残す改善が必要）
- デモ AI は決まった手順で結果を作るもので、教材の中身を理解して判断しているわけではありません
