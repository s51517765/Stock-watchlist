import datetime
import requests
from .models import PriceHistory, ScoreSetting
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def fetch_yahoo_chart(symbol):
    """Yahoo Finance APIから株価・配当・銘柄名を取得する（標準ライブラリ版）

    戻り値:
        name (str): 銘柄名（APIから取れない場合はコード）
        price_list (list): [{'date': datetime.date, 'close': float}, ...] のリスト
    """
    symbol_str = str(symbol)
    if not symbol_str.endswith(".T"):
        symbol_str = symbol_str + ".T"

    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol_str}?range=1y&interval=1d&events=div"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"取得失敗: {symbol_str} (Code: {response.status_code})")
            return None, []

        json_data = response.json()
        if (
            not json_data.get("chart")
            or not json_data["chart"].get("result")
            or len(json_data["chart"]["result"]) == 0
        ):
            print(f"データなし: {symbol_str}")
            return None, []

        data = json_data["chart"]["result"][0]

        # 銘柄名やメタデータの取得
        meta = data.get("meta", {})
        name = meta.get("longName") or meta.get("shortName") or symbol_str

        # タイムスタンプと終値の取得
        timestamps = data.get("timestamp", [])
        quote = data["indicators"]["quote"][0]
        closes = quote.get("close", [])

        price_list = []
        for ts, price in zip(timestamps, closes):
            if price is not None:
                # タイムスタンプを日付オブジェクトに変換
                dt = datetime.datetime.fromtimestamp(ts).date()
                price_list.append(
                    {
                        "date": dt,
                        "close": round(float(price), 2),
                    }
                )

        return name, price_list

    except Exception as e:
        print(f"例外発生 ({symbol_str}): {e}")
        return None, []


def calculate_indicators(stock):
    """ボリンジャーバンドや利回りなどの指標を計算してStockモデルに保存する"""
    from .models import PriceHistory

    # データベースから直近の価格履歴を取得（日付順）
    histories = list(PriceHistory.objects.filter(stock=stock).order_by("date"))
    if not histories:
        return

    # 現在株価（一番新しい日の終値）
    latest_history = histories[-1]
    stock.current_price = latest_history.close_price
    # stock.updated_at = datetime.datetime.now()

    # 利回りの計算 (年間配当 ÷ 現在株価 * 100)
    if stock.dividend_amount and stock.current_price:
        stock.dividend_yield = round(
            (Decimal(stock.dividend_amount) / Decimal(stock.current_price))
            * Decimal("100"),
            2,
        )
    else:
        stock.dividend_yield = 0

    # ボリンジャーバンド（直近25日間の平均と標準偏差）の簡易計算
    closes = [h.close_price for h in histories]

    if len(closes) >= 25:
        period_closes = closes[-25:]
        # float型に変換して平均・分散を計算
        mean = sum(float(x) for x in period_closes) / len(period_closes)
        variance = sum((float(x) - mean) ** 2 for x in period_closes) / len(
            period_closes
        )
        std_dev = variance**0.5

        stock.bollinger_band_sigma = round(std_dev, 1)

        if std_dev > 0:
            stock.bollinger_band_position = round(
                (float(stock.current_price) - mean) / std_dev, 2
            )
            # 判定の自動付与
            if stock.bollinger_band_position <= -2.0:
                stock.judgement = "買い"
            elif stock.bollinger_band_position >= 2.0:
                stock.judgement = "売り"
            else:
                stock.judgement = "中立"
        else:
            stock.bollinger_band_position = 0.0
            stock.judgement = "-"

    stock.save()


def update_stock_prices():
    """登録されている全銘柄の価格を一括更新する関数"""
    from .models import Stock, PriceHistory

    stocks = Stock.objects.all()
    for stock in stocks:
        _, price_list = fetch_yahoo_chart(stock.code)
        if price_list:
            # 過去データを更新・保存
            for item in price_list[-75:]:  # 直近75日分
                PriceHistory.objects.update_or_create(
                    stock=stock,
                    date=item["date"],
                    defaults={"close_price": item["close"]},
                )
            # 指標を再計算
            calculate_indicators(stock)


def refresh_stock_data(stock, history_limit=75):
    """
    指定した Stock インスタンスの株価履歴を取得・保存し、指標を再計算する。
    戻り値: 更新に成功したら True、取得できなければ False
    """
    _, price_list = fetch_yahoo_chart(stock.code)
    if not price_list:
        return False

    for item in price_list[-history_limit:]:
        PriceHistory.objects.update_or_create(
            stock=stock,
            date=item["date"],
            defaults={"close_price": item["close"]},
        )

    # calculate_indicators 側で stock.updated_at は変更されない前提
    calculate_indicators(stock)
    return True


def calculate_stock_score(stock, setting: ScoreSetting | None = None) -> int | None:
    if setting is None:
        setting = ScoreSetting.get_solo()

    if stock.dividend_yield is None:
        return None

    symbol_map = setting.get_symbol_map()

    def to_coef(val: str | None) -> Decimal:
        if not val:
            return Decimal("0")
        return symbol_map.get(str(val).strip(), Decimal("0"))

    try:
        yld = Decimal(str(stock.dividend_yield))
    except InvalidOperation:
        return None

    c_div = to_coef(stock.consecutive_dividend_increases)
    perf = to_coef(stock.business_performance)
    policy = to_coef(stock.dividend_policy)

    try:
        payout = (
            Decimal(str(stock.dividend_payout_ratio))
            if stock.dividend_payout_ratio is not None
            else Decimal("0")
        )
    except InvalidOperation:
        payout = Decimal("0")

    payout_factor = max(Decimal("100") - payout, Decimal("0"))

    # 利回り^2 * 連続増配 * 業績推移 * max(100 - 配当性向, 0) + 配当政策
    raw_score = (yld**2) * c_div * perf * payout_factor + policy
    return int(raw_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_score_css_class(score: int | None, setting: ScoreSetting | None = None) -> str:
    if score is None:
        return ""
    if setting is None:
        setting = ScoreSetting.get_solo()

    if score >= setting.threshold_high:
        return "score-high"
    if score >= setting.threshold_mid:
        return "score-mid"
    if score >= setting.threshold_low:
        return "score-low"
    return "score-below"
