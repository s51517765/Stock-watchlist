import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone
from stocks.models import Stock
from stocks.utils import refresh_stock_data

# 必要に応じて「YYYY-MM-DD」形式で追加・更新する祝日リスト
HOLIDAYS = {
    "2026-11-23",  # 勤労感謝の日
    "2026-12-31",  # 年末休場目安
    "2027-01-01",  # 元日（金）
    "2027-01-11",  # 成人の日（月）
    "2027-02-11",  # 建国記念の日（木）
    "2027-02-23",  # 天皇誕生日（火）
    "2027-03-21",  # 春分の日（日）
    "2027-03-22",  # 振替休日（月）
    "2027-04-29",  # 昭和の日（木）
    "2027-05-03",  # 憲法記念日（月）
    "2027-05-04",  # みどりの日（火）
    "2027-05-05",  # こどもの日（水）
    "2027-07-19",  # 海の日（月）
    "2027-08-11",  # 山の日（水）
    "2027-09-20",  # 敬老の日（月）
    "2027-09-23",  # 秋分の日（木）
    "2027-10-11",  # スポーツの日（月）
    "2027-11-03",  # 文化の日（水）
    "2027-11-23",  # 勤労感謝の日（火）
    "2027-12-31",  # 東証年末休業日（金）
}


class Command(BaseCommand):
    help = "登録済み銘柄の株価を更新し、失敗した銘柄のみリトライします（土日祝はスキップ、--force で強制実行）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sleep",
            type=float,
            default=1.0,
            help="通常ループでの1銘柄ごとの待機秒数（デフォルト: 1秒）",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=45,
            help="取得・保存する直近データの件数目安（デフォルト: 45件）",
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=2,
            help="失敗銘柄のリトライ回数（デフォルト: 2回）",
        )
        parser.add_argument(
            "--retry-wait",
            type=float,
            default=3.0,
            help="リトライ前の待機秒数（デフォルト: 3.0秒）",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="土日や祝日であっても強制的に更新を実行します。",
        )

    def handle(self, *args, **options):
        sleep_sec = options["sleep"]
        history_limit = options["limit"]
        max_retries = options["retries"]
        retry_wait = options["retry_wait"]
        force = options["force"]

        start_dt = timezone.localtime(timezone.now())
        start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        today_str = start_dt.strftime("%Y-%m-%d")

        is_weekend = start_dt.weekday() >= 5  # 5=土曜, 6=日曜
        is_holiday = today_str in HOLIDAYS

        if (is_weekend or is_holiday) and not force:
            reason = "土日" if is_weekend else "祝日"
            self.stdout.write(
                f"[{start_str}] {reason}（{today_str}）のため更新をスキップしました（強制実行するには --force を指定）。"
            )
            return

        if (start_dt.hour < 9 or start_dt.hour > 16) and not force:
            reason = "時間外"
            self.stdout.write(
                f"[{start_str}] {reason}（{today_str}）のため更新をスキップしました。"
            )
            return

        stocks = list(Stock.objects.all().order_by("code"))
        total = len(stocks)

        ok_cnt = 0
        failed_stocks = []  # 失敗した Stock を保持

        mode_label = (
            "（--force 強制実行）" if force and (is_weekend or is_holiday) else ""
        )
        self.stdout.write(f"開始時刻: {start_str}{mode_label}")
        self.stdout.write(f"対象銘柄数: {total} 件の更新を開始します。")

        # 1. 初回巡回
        for idx, stock in enumerate(stocks, start=1):
            try:
                close_old_connections()
                if refresh_stock_data(stock, history_limit=history_limit):
                    ok_cnt += 1
                    self.stdout.write(f"[{idx}/{total}] {stock.code} {stock.name}: OK")
                else:
                    failed_stocks.append(stock)
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{idx}/{total}] {stock.code} {stock.name}: 取得なし（リトライ対象）"
                        )
                    )
            except Exception as e:
                failed_stocks.append(stock)
                self.stderr.write(
                    self.style.ERROR(
                        f"[{idx}/{total}] {stock.code} {stock.name}: 失敗（リトライ対象） - {e}"
                    )
                )

            if sleep_sec > 0 and idx < total:
                time.sleep(sleep_sec)

        # 2. 失敗した銘柄のみリトライ
        for attempt in range(1, max_retries + 1):
            if not failed_stocks:
                break

            self.stdout.write(
                self.style.WARNING(
                    f"--- リトライ {attempt}/{max_retries}回目: {len(failed_stocks)} 件（{retry_wait}秒待機） ---"
                )
            )
            time.sleep(retry_wait)

            next_failed = []
            for stock in failed_stocks:
                try:
                    close_old_connections()
                    if refresh_stock_data(stock, history_limit=history_limit):
                        ok_cnt += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  [リトライ成功] {stock.code} {stock.name}: OK"
                            )
                        )
                    else:
                        next_failed.append(stock)
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [リトライ失敗] {stock.code} {stock.name}: 取得なし"
                            )
                        )
                except Exception as e:
                    next_failed.append(stock)
                    self.stderr.write(
                        self.style.ERROR(
                            f"  [リトライ失敗] {stock.code} {stock.name}: {e}"
                        )
                    )

                if sleep_sec > 0:
                    time.sleep(sleep_sec)

            failed_stocks = next_failed

        # 3. 最終結果
        final_ng = len(failed_stocks)
        if final_ng == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"完了: 全 {ok_cnt} 件 更新成功（リトライ後エラー 0件）"
                )
            )
        else:
            ng_codes = ", ".join(f"{s.code}({s.name})" for s in failed_stocks)
            self.stdout.write(
                self.style.WARNING(
                    f"完了: 成功 {ok_cnt} 件 / 最終失敗 {final_ng} 件 -> {ng_codes}"
                )
            )

        end_dt = timezone.localtime(timezone.now())
        end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        self.stdout.write(f"終了時刻: {end_str}")

        time_lap = end_dt - start_dt
        total_seconds = int(time_lap.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self.stdout.write(
            f"所要時間: {hours:02d}:{minutes:02d}:{seconds:02d}（{total_seconds}秒）"
        )
