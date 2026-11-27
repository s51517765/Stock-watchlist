import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from .models import Stock, Holiday, AppSetting, PriceHistory, ScoreSetting
from .utils import (
    fetch_yahoo_chart,
    calculate_indicators,
    refresh_stock_data,
    calculate_stock_score,
    get_score_css_class,
    get_sigma_inline_style,
    calculate_expected_dividend,
)
from .forms import ScoreSettingForm


@login_required
def stock_list(request):
    """銘柄一覧画面"""
    sort_key = request.GET.get("sort", "code")
    order = request.GET.get("order", "asc")  # デフォルトは昇順

    if sort_key == "code":
        field = "code"
    elif sort_key == "yield":
        field = "dividend_yield"
    elif sort_key == "bb":
        field = "bollinger_band_position"
    else:
        sort_key = "code"
        field = "code"

    order_field = f"-{field}" if order == "desc" else field

    # ソート済みのクエリセットをリスト化し、そのまま score_class を付与する
    stocks = list(Stock.objects.all().order_by(order_field, "code"))

    setting = ScoreSetting.get_solo()
    for stock in stocks:
        stock.score_class = get_score_css_class(stock.evaluation_score, setting)
        stock.sigma_style = get_sigma_inline_style(
            stock.bollinger_band_position, setting
        )

    next_order = "desc" if order == "asc" else "asc"

    context = {
        "stocks": stocks,
        "setting": setting,
        "current_sort": sort_key,
        "current_order": order,
        "next_order": next_order,
    }
    return render(request, "stocks/stock_list.html", context)


@login_required
def stock_create(request, key_id=None):
    """新規登録画面"""
    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        name = request.POST.get("name", "").strip()

        # すでに同じ code が登録されている場合は登録せずフォームに戻す
        if code and Stock.objects.filter(code=code).exists():
            messages.error(
                request,
                f"銘柄コード【{code}】{Stock.objects.filter(code=code).first().name} はすでに登録されています。",
            )
            context = {
                "form_data": request.POST,
            }
            return render(request, "stocks/stock_form.html", context)

        fetched_name, price_list = fetch_yahoo_chart(code)
        if not name:
            name = fetched_name or code

        payout_ratio = request.POST.get("dividend_payout_ratio")
        payout_ratio = int(payout_ratio) if payout_ratio else None

        # 権利月の取得（チェックされた月をリストで取得し、"/" で結合）
        kenri_list = request.POST.getlist("kenri_tsuki")
        kenri_tsuki_str = "/".join(kenri_list) if kenri_list else ""

        # ポジションの取得（チェックされたポジションをリストで取得し、"/" で結合）
        selected_positions = request.POST.getlist("position")
        position = "/".join(selected_positions) if selected_positions else "-"

        # 見込み配当の計算
        dividend_amount_raw = request.POST.get("dividend_amount")
        dividend_amount = float(dividend_amount_raw) if dividend_amount_raw else None
        nisa, tokutei = _get_total_shares_from_post(request.POST)
        expected_dividend = calculate_expected_dividend(nisa, tokutei, dividend_amount)

        stock, created = Stock.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "dividend_amount": dividend_amount,
                "position": position,
                "position_nisa": _parse_int(request.POST.get("position_nisa")) or None,
                "position_matsui": _parse_int(request.POST.get("position_matsui"))
                or None,
                "position_sbi": _parse_int(request.POST.get("position_sbi")) or None,
                "position_monex": _parse_int(request.POST.get("position_monex"))
                or None,
                "position_other": _parse_int(request.POST.get("position_other"))
                or None,
                "expected_dividend": expected_dividend,
                "target_price": request.POST.get("target_price") or None,
                "consecutive_dividend_increases": request.POST.get(
                    "consecutive_dividend_increases", "-"
                ),
                "business_performance": request.POST.get("business_performance", "-"),
                "dividend_policy": request.POST.get("dividend_policy", "-"),
                "dividend_payout_ratio": payout_ratio,
                "kenri_tsuki": kenri_tsuki_str,
                "yuutai": request.POST.get("yuutai", ""),
                "memo": request.POST.get("memo", ""),
                "updated_at": datetime.datetime.now(),
            },
        )

        if price_list:
            recent_prices = price_list[-75:]
            for item in recent_prices:
                PriceHistory.objects.update_or_create(
                    stock=stock,
                    date=item["date"],
                    defaults={"close_price": item["close"]},
                )
            calculate_indicators(stock)

        return redirect("stock_list")

    context = {
        "months": list(range(1, 13)),
        "selected_months": [],
    }
    return render(request, "stocks/stock_form.html", context)


@login_required
def stock_edit(request, code):
    """銘柄編集画面"""
    stock = get_object_or_404(Stock, code=code)

    # 既存の権利月文字列を分解してリスト化（例: "3/9" -> ['3', '9']）
    selected_months = stock.kenri_tsuki.split("/") if stock.kenri_tsuki else []

    # 既存のポジション文字列を分解してリスト化（例: "NISA/SBI" -> ['NISA', 'SBI']）
    selected_positions = (
        stock.position.split("/") if stock.position and stock.position != "-" else []
    )

    if request.method == "POST":
        stock.name = request.POST.get("name", "").strip()
        selected_positions_post = request.POST.getlist("position")

        # ポジション
        stock.position = (
            "/".join(selected_positions_post) if selected_positions_post else "-"
        )

        # ファンダ、配当
        dividend_amount_raw = request.POST.get("dividend_amount")
        stock.dividend_amount = (
            float(dividend_amount_raw) if dividend_amount_raw else None
        )
        stock.target_price = request.POST.get("target_price") or None

        stock.consecutive_dividend_increases = request.POST.get(
            "consecutive_dividend_increases", "-"
        )
        stock.business_performance = request.POST.get("business_performance", "-")
        stock.dividend_policy = request.POST.get("dividend_policy", "-")

        payout_ratio = request.POST.get("dividend_payout_ratio")
        stock.dividend_payout_ratio = int(payout_ratio) if payout_ratio else None

        # 配当見込み

        stock.position_nisa = _parse_int(request.POST.get("position_nisa")) or None
        stock.position_matsui = _parse_int(request.POST.get("position_matsui")) or None
        stock.position_sbi = _parse_int(request.POST.get("position_sbi")) or None
        stock.position_monex = _parse_int(request.POST.get("position_monex")) or None
        stock.position_other = _parse_int(request.POST.get("position_other")) or None

        tokutei = (
            (stock.position_matsui or 0)
            + (stock.position_sbi or 0)
            + (stock.position_monex or 0)
            + (stock.position_other or 0)
        )
        stock.expected_dividend = calculate_expected_dividend(
            (stock.position_nisa or 0), tokutei, stock.dividend_amount
        )

        # 権利月の更新
        kenri_list = request.POST.getlist("kenri_tsuki")
        stock.kenri_tsuki = "/".join(kenri_list) if kenri_list else ""

        stock.yuutai = request.POST.get("yuutai", "")
        stock.memo = request.POST.get("memo", "")

        stock.updated_at = datetime.datetime.now()
        stock.save()

        calculate_indicators(stock)
        return redirect("stock_list")

    context = {
        "stock": stock,
        "months": list(range(1, 13)),
        "selected_months": selected_months,
        "selected_positions": selected_positions,
    }
    return render(request, "stocks/stock_form.html", context)


@login_required
def stock_update(request, code):
    """指定した銘柄の株価データをAPIから再取得して更新する（単体更新）"""
    stock = get_object_or_404(Stock, code=code)

    if not refresh_stock_data(stock, history_limit=75):
        print(f"警告: {stock.code} のデータ取得に失敗したため更新をスキップしました。")

    return redirect("stock_list")


@login_required
def stock_delete(request, code):
    """指定した銘柄を削除する"""
    stock = get_object_or_404(Stock, code=code)
    stock.delete()
    return redirect("stock_list")


@login_required
def score_settings(request):
    setting = ScoreSetting.get_solo()

    if request.method == "POST":
        form = ScoreSettingForm(request.POST, instance=setting)
        if form.is_valid():
            setting = form.save()

            # 全銘柄のスコアを再計算して一括更新
            stocks = list(Stock.objects.all())
            for stock in stocks:
                stock.evaluation_score = calculate_stock_score(stock, setting)
            if stocks:
                Stock.objects.bulk_update(stocks, ["evaluation_score"])

            messages.success(request, "設定を保存し、全銘柄のスコアを再計算しました。")
            return redirect("score_settings")
    else:
        form = ScoreSettingForm(instance=setting)

    return render(
        request, "stocks/score_settings.html", {"form": form, "setting": setting}
    )


def _parse_int(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _get_total_shares_from_post(post_data) -> int:
    fields = [
        "position_matsui",
        "position_sbi",
        "position_monex",
        "position_other",
    ]

    tokutei = sum(_parse_int(post_data.get(name)) for name in fields)
    nisa = _parse_int(post_data.get("position_nisa"))
    return nisa, tokutei
