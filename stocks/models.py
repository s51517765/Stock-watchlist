from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Holiday(models.Model):
    """休日設定マスタ（yyyy/mm/dd形式の手動登録）"""

    date = models.DateField(primary_key=True, verbose_name="休日")
    description = models.CharField(max_length=100, blank=True, verbose_name="名称")

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return str(self.date)


class Stock(models.Model):
    """監視銘柄マスタ"""

    POSITION_CHOICES = [
        ("-", "-"),
        ("NISA", "NISA"),
        ("松井", "松井"),
        ("SBI", "SBI"),
        ("マネックス", "マネックス"),
        ("その他", "その他"),
    ]

    # 必須
    code = models.CharField(max_length=6, primary_key=True, verbose_name="コード")

    # 任意
    name = models.CharField(max_length=20, blank=True, verbose_name="銘柄名")
    position = models.CharField(
        max_length=10, choices=POSITION_CHOICES, blank=True, verbose_name="ポジション"
    )
    target_price = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, verbose_name="目標株価"
    )
    dividend_amount = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="配当金額"
    )

    # 定性・評価項目（入力は官能的、判定時に数値化）
    judgement = models.CharField(max_length=5, blank=True, verbose_name="判定")
    consecutive_dividend_increases = models.CharField(
        max_length=5, default="-", verbose_name="連続増配(〇/△/×/-)"
    )
    business_performance = models.CharField(
        max_length=5, default="-", verbose_name="業績推移(〇/△/×/-)"
    )
    dividend_policy = models.CharField(
        max_length=10,
        default="-",
        verbose_name="配当政策(〇増配/△非減配/-)",
    )

    dividend_payout_ratio = models.IntegerField(
        null=True, blank=True, verbose_name="配当性向(%)"
    )
    kenri_tsuki = models.CharField(
        max_length=50, blank=True, verbose_name="権利月（複数可）"
    )  # 例: "3,9"
    yuutai = models.TextField(blank=True, verbose_name="優待")
    memo = models.TextField(blank=True, verbose_name="メモ")

    # 計算・キャッシュ項目
    current_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="現在株価"
    )
    dividend_yield = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="配当利回り(%)",
    )
    bollinger_band_position = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="ボリンジャーバンド位置(σ)",
    )
    bollinger_band_sigma = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True, verbose_name="σ値"
    )
    evaluation_score = models.IntegerField(
        null=True, blank=True, verbose_name="評価指数"
    )

    # ポジション
    position_nisa = models.IntegerField(null=True, blank=True, verbose_name="NISA")
    position_matsui = models.IntegerField(null=True, blank=True, verbose_name="松井")
    position_sbi = models.IntegerField(null=True, blank=True, verbose_name="SBI")
    position_monex = models.IntegerField(
        null=True, blank=True, verbose_name="マネックス"
    )
    position_other = models.IntegerField(null=True, blank=True, verbose_name="その他")

    expected_dividend = models.IntegerField(
        null=True, blank=True, verbose_name="見込み配当"
    )

    updated_at = models.DateTimeField(auto_now=False, verbose_name="更新日")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PriceHistory(models.Model):
    """価格推移（リングバッファ用・過去75営業日）"""

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="price_histories"
    )
    date = models.DateField(verbose_name="営業日")
    close_price = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name="終値"
    )

    class Meta:
        unique_together = ("stock", "date")
        ordering = ["-date"]


class AppSetting(models.Model):
    """アプリケーション設定（JSON形式保存）"""

    key = models.CharField(max_length=50, unique=True, verbose_name="設定キー")
    value = models.JSONField(verbose_name="設定値")

    def __str__(self):
        return self.key


class ScoreSetting(models.Model):
    # 記号変換設定
    score_circle = models.DecimalField(
        "〇のスコア", max_digits=5, decimal_places=2, default=Decimal("1.00")
    )
    score_triangle = models.DecimalField(
        "△のスコア", max_digits=5, decimal_places=2, default=Decimal("0.40")
    )
    score_hyphen = models.DecimalField(
        "-のスコア", max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    score_cross = models.DecimalField(
        "×のスコア", max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    # 配当政策加点
    div_circle = models.DecimalField(
        "〇のスコア", max_digits=3, decimal_places=0, default=Decimal("500")
    )
    div_triangle = models.DecimalField(
        "△のスコア", max_digits=3, decimal_places=0, default=Decimal("200")
    )

    # 判定セル色分け閾値
    threshold_high = models.IntegerField("高評価（緑）以上", default=1300)
    threshold_mid = models.IntegerField("中評価（黄）以上", default=900)
    threshold_low = models.IntegerField("基準内（白/薄色）以上", default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "スコア設定"
        verbose_name_plural = "スコア設定"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_symbol_map(self) -> dict[str, Decimal]:
        return {
            "〇": self.score_circle,
            "○": self.score_circle,  # 全角丸の表記ゆれ対策
            "△": self.score_triangle,
            "-": self.score_hyphen,
            "ー": self.score_hyphen,
            "×": self.score_cross,
            "〇増配": self.div_circle,
            "△非減配": self.div_triangle,
        }

    # σ値 閾値設定
    sigma_pos_2_threshold = models.FloatField("σ上限強（以上）", default=2.0)
    sigma_pos_15_threshold = models.FloatField("σ上限弱（以上）", default=1.5)
    sigma_neg_15_threshold = models.FloatField("σ下限弱（以下）", default=-1.5)
    sigma_neg_2_threshold = models.FloatField("σ下限強（以下）", default=-2.0)

    # σ値 背景色・文字色設定
    sigma_pos_2_bg = models.CharField("σ>=2 背景色", max_length=20, default="#32ff32")
    sigma_pos_2_fg = models.CharField("σ>=2 文字色", max_length=20, default="#FFFFFF")

    sigma_pos_15_bg = models.CharField(
        "σ>=1.5 背景色", max_length=20, default="#cdfac9"
    )
    sigma_pos_15_fg = models.CharField(
        "σ>=1.5 文字色", max_length=20, default="#001330"
    )

    sigma_neg_15_bg = models.CharField(
        "σ<=-1.5 背景色", max_length=20, default="#f8a25b"
    )
    sigma_neg_15_fg = models.CharField(
        "σ<=-1.5 文字色", max_length=20, default="#984c0c"
    )

    sigma_neg_2_bg = models.CharField("σ<=-2 背景色", max_length=20, default="#fd5521")
    sigma_neg_2_fg = models.CharField("σ<=-2 文字色", max_length=20, default="#FFFFFF")

    sigma_other_bg = models.CharField(
        "σその他 背景色", max_length=20, default="#ffffff"
    )
    sigma_other_fg = models.CharField(
        "σその他 文字色", max_length=20, default="#212529"
    )
