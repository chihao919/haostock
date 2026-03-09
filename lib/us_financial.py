"""US stock financial analysis using yfinance."""

import yfinance as yf


def fetch_us_financials(ticker: str) -> dict:
    """Fetch all financial data from yfinance."""
    stock = yf.Ticker(ticker)
    return {
        "info": stock.info or {},
        "income_stmt": stock.income_stmt,
        "balance_sheet": stock.balance_sheet,
        "cashflow": stock.cashflow,
    }


def analyze_us_revenue_growth(info: dict) -> dict:
    """Analyze revenue growth from yfinance info."""
    revenue_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")

    result = {
        "revenue_growth_pct": round(revenue_growth * 100, 2) if revenue_growth else None,
        "earnings_growth_pct": round(earnings_growth * 100, 2) if earnings_growth else None,
        "pass": False,
    }
    result["pass"] = bool(result["revenue_growth_pct"] and result["revenue_growth_pct"] > 10)
    return result


def analyze_us_cash_flow_health(cashflow, income_stmt) -> dict:
    """Analyze OCF, FCF, and FCF conversion ratio."""
    result = {"ocf": None, "fcf": None, "fcf_conversion": None, "ocf_positive": False, "pass": False}

    if cashflow is None or cashflow.empty:
        return {**result, "detail": "No cash flow data"}

    try:
        ocf_row = cashflow.loc["Operating Cash Flow"] if "Operating Cash Flow" in cashflow.index else None
        capex_row = cashflow.loc["Capital Expenditure"] if "Capital Expenditure" in cashflow.index else None

        if ocf_row is not None and len(ocf_row) > 0:
            latest_ocf = float(ocf_row.iloc[0])
            result["ocf"] = round(latest_ocf / 1e6, 2)
            result["ocf_positive"] = latest_ocf > 0

            fcf = None
            if capex_row is not None and len(capex_row) > 0:
                latest_capex = float(capex_row.iloc[0])
                fcf = latest_ocf + latest_capex
                result["fcf"] = round(fcf / 1e6, 2)

            # FCF Conversion = FCF / Net Income (> 80% is good)
            if fcf is not None and income_stmt is not None and not income_stmt.empty:
                ni_row = None
                for label in ["Net Income", "Net Income Continuous Operations", "Net Income Common Stockholders"]:
                    if label in income_stmt.index:
                        ni_row = income_stmt.loc[label]
                        break
                if ni_row is not None and len(ni_row) > 0:
                    net_income = float(ni_row.iloc[0])
                    if net_income > 0:
                        result["fcf_conversion"] = round(fcf / net_income * 100, 1)

            if len(ocf_row) >= 2:
                result["ocf_trending_up"] = float(ocf_row.iloc[0]) > float(ocf_row.iloc[1])

        # Pass: OCF positive AND FCF conversion > 80%
        fcf_ok = result["fcf_conversion"] is not None and result["fcf_conversion"] >= 80
        result["pass"] = result["ocf_positive"] and fcf_ok
        result["criteria"] = {
            "ocf_positive": result["ocf_positive"],
            "fcf_conversion_ok": fcf_ok,
        }
    except Exception:
        pass

    return result


def analyze_us_financial_strength(income_stmt, balance_sheet) -> dict:
    """Analyze interest coverage, CCC, and ROIC (replaces simple current ratio)."""
    result = {
        "interest_coverage": None,
        "cash_conversion_cycle": None,
        "roic": None,
        "current_ratio": None,
        "pass": False,
    }

    if income_stmt is None or income_stmt.empty:
        return {**result, "detail": "No income statement data"}

    try:
        def get_inc(name):
            if name in income_stmt.index and len(income_stmt.loc[name]) > 0:
                return float(income_stmt.loc[name].iloc[0])
            return None

        def get_bs(name):
            if balance_sheet is not None and not balance_sheet.empty:
                if name in balance_sheet.index and len(balance_sheet.loc[name]) > 0:
                    return float(balance_sheet.loc[name].iloc[0])
            return None

        # 1. Interest Coverage = EBIT / Interest Expense (> 10x)
        ebit = get_inc("EBIT")
        interest_exp = get_inc("Interest Expense")
        if interest_exp is None:
            interest_exp = get_inc("Interest Expense Non Operating")
        # Handle NaN from yfinance
        import math
        if interest_exp is not None and math.isnan(interest_exp):
            interest_exp = None
        if ebit and interest_exp and interest_exp != 0:
            interest_abs = abs(interest_exp)
            if interest_abs > 0:
                result["interest_coverage"] = round(ebit / interest_abs, 1)

        # 2. Cash Conversion Cycle = DIO + DSO - DPO (< 60 days)
        revenue = get_inc("Total Revenue") or get_inc("Operating Revenue")
        cogs = get_inc("Cost Of Revenue")
        receivables = get_bs("Accounts Receivable") or get_bs("Receivables")
        inventory = get_bs("Inventory")
        payables = get_bs("Accounts Payable") or get_bs("Payables")

        if revenue and revenue > 0:
            dso = round(receivables / revenue * 365, 1) if receivables else 0
            dio = round(inventory / cogs * 365, 1) if (inventory and cogs and cogs > 0) else 0
            dpo = round(payables / cogs * 365, 1) if (payables and cogs and cogs > 0) else 0
            result["cash_conversion_cycle"] = round(dio + dso - dpo, 1)

        # 3. ROIC = NOPAT / Invested Capital (> 15%)
        # NOPAT = EBIT * (1 - tax_rate), approx tax_rate from effective tax
        tax = get_inc("Tax Provision")
        pretax = get_inc("Pretax Income")
        if ebit and pretax and pretax > 0 and tax is not None:
            tax_rate = tax / pretax
            nopat = ebit * (1 - tax_rate)

            total_equity = get_bs("Stockholders Equity")
            total_debt = get_bs("Total Debt")
            cash = get_bs("Cash And Cash Equivalents")
            if total_equity is not None and total_debt is not None:
                invested_capital = total_equity + total_debt - (cash or 0)
                if invested_capital > 0:
                    result["roic"] = round(nopat / invested_capital * 100, 2)

        # 4. Current ratio (still report it, just not primary criterion)
        ca = get_bs("Current Assets")
        cl = get_bs("Current Liabilities")
        if ca and cl and cl != 0:
            result["current_ratio"] = round(ca / cl * 100, 1)

        # Pass criteria: interest_coverage > 10 OR no debt
        ic_ok = (result["interest_coverage"] is not None and result["interest_coverage"] >= 10) or \
                (interest_exp is None or interest_exp == 0)
        # CCC < 60 days (or None for service companies = ok)
        ccc_ok = result["cash_conversion_cycle"] is None or result["cash_conversion_cycle"] < 60
        # ROIC > 15%
        roic_ok = result["roic"] is not None and result["roic"] >= 15

        result["pass"] = bool(ic_ok and roic_ok)
        result["criteria"] = {
            "interest_coverage_ok": bool(ic_ok),
            "ccc_ok": bool(ccc_ok),
            "roic_ok": bool(roic_ok),
        }
    except Exception:
        pass

    return result


def analyze_us_profitability(income_stmt, info: dict) -> dict:
    """Analyze net profit margin, ROE, gross margin."""
    result = {
        "net_profit_margin": None,
        "roe": None,
        "gross_margin": None,
        "pass": False,
    }

    profit_margin = info.get("profitMargins")
    roe = info.get("returnOnEquity")
    gross_margin = info.get("grossMargins")

    if profit_margin is not None:
        result["net_profit_margin"] = round(profit_margin * 100, 2)
    if roe is not None:
        result["roe"] = round(roe * 100, 2)
    if gross_margin is not None:
        result["gross_margin"] = round(gross_margin * 100, 2)

    npm_ok = result["net_profit_margin"] is not None and result["net_profit_margin"] >= 2
    roe_ok = result["roe"] is not None and result["roe"] >= 20
    result["pass"] = bool(npm_ok and roe_ok)
    result["criteria"] = {"net_profit_margin_ok": bool(npm_ok), "roe_ok": bool(roe_ok)}
    return result


def estimate_us_valuation(info: dict) -> dict:
    """Valuation metrics from yfinance info."""
    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "peg_ratio": info.get("pegRatio"),
        "market_cap": info.get("marketCap"),
        "target_mean_price": info.get("targetMeanPrice"),
        "current_price": info.get("currentPrice"),
    }


async def analyze_stock(ticker: str) -> dict:
    """Full financial analysis for a US stock."""
    import asyncio
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, fetch_us_financials, ticker)

    info = data["info"]
    income_stmt = data["income_stmt"]
    balance_sheet = data["balance_sheet"]
    cashflow = data["cashflow"]

    revenue_analysis = analyze_us_revenue_growth(info)
    cashflow_analysis = analyze_us_cash_flow_health(cashflow, income_stmt)
    strength_analysis = analyze_us_financial_strength(income_stmt, balance_sheet)
    profit_analysis = analyze_us_profitability(income_stmt, info)
    valuation = estimate_us_valuation(info)

    checks = [
        revenue_analysis["pass"],
        cashflow_analysis["pass"],
        strength_analysis["pass"],
        profit_analysis["pass"],
    ]
    score = sum(1 for c in checks if c)

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "market": "US",
        "score": f"{score}/4",
        "overall_pass": score >= 3,
        "revenue_growth": revenue_analysis,
        "cash_flow": cashflow_analysis,
        "financial_strength": strength_analysis,
        "profitability": profit_analysis,
        "valuation": valuation,
    }
