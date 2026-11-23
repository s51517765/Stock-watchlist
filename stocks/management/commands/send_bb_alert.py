from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from stocks.models import Stock, Holiday
from datetime import date
import time


class Command(BaseCommand):
    help = "ボリンジャーバンド乖離銘柄をメール送信する"

    def handle(self, *args, **options):
        today = date.today()
        # 休日チェック
        if Holiday.objects.filter(date=today).exists():
            self.stdout.write("本日は休日のためスキップします。")
            return

        # 2σ以上または-2σ以下の銘柄を抽出
        target_stocks = []
        for stock in Stock.objects.all():
            if stock.bollinger_band_position is not None:
                if (
                    stock.bollinger_band_position >= 2.0
                    or stock.bollinger_band_position <= -2.0
                ):
                    target_stocks.append(stock)

        if target_stocks:
            message_body = "【ボリンジャーバンド乖離アラート】\n\n"
            for s in target_stocks:
                message_body += f"コード: {s.code} | 銘柄名: {s.name} | 株価: {s.current_price} | BB位置: {s.bollinger_band_position}σ\n"
        else:
            message_body = (
                "本日のボリンジャーバンド乖離（±2σ以上）対象銘柄は0件でした。"
            )

        # メール送信実行（リトライ処理付き）
        success = False
        for attempt in range(2):
            try:
                send_mail(
                    subject="【株価監視ツール】BB乖離通知",
                    message=message_body,
                    from_email="your-email@gmail.com",
                    recipient_list=["target-email@gmail.com"],
                    fail_silently=False,
                )
                success = True
                break
            except Exception as e:
                self.stdout.write(f"メール送信エラー (試行 {attempt+1}): {e}")
                if attempt == 0:
                    time.sleep(900)  # 15分後にリトライ (1回のみ)

        if not success:
            self.stdout.write("メール送信が最終的に失敗しました。")
