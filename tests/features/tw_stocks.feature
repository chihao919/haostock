Feature: Taiwan Stock Portfolio
  As an investor
  I want to query my Taiwan stock positions with real-time prices
  So that I can see my current P&L in both TWD and USD

  Background:
    Given the Notion TW Stocks database contains the following positions:
      | account    | ticker  | name   | shares | avg_cost |
      | Yongfeng_B | 2330.TW | 台積電 | 5000   | 854.56   |
      | Cathay_TW  | 0050.TW | 元大台灣50 | 4075 | 61.26  |
    And the USD/TWD exchange rate is 32.15

  Scenario: Calculate P&L in TWD for Taiwan stocks
    Given the current price of "2330.TW" is 900.00
    When I request GET /api/stocks/tw
    Then the position "2330.TW" in account "Yongfeng_B" should have:
      | field              | value     |
      | market_value_twd   | 4500000   |
      | cost_basis_twd     | 4272800   |
      | unrealized_pl_twd  | 227200    |

  Scenario: Convert TWD values to USD
    Given the current price of "2330.TW" is 900.00
    And the USD/TWD exchange rate is 32.15
    When I request GET /api/stocks/tw
    Then the position "2330.TW" should have "market_value_usd" equal to 139969.52

  Scenario: Response includes exchange rate
    When I request GET /api/stocks/tw
    Then the response should contain "usdtwd_rate" equal to 32.15

  Scenario: Summary totals in both currencies
    Given all TW stock prices are fetched successfully
    When I request GET /api/stocks/tw
    Then the summary should contain:
      | field                  |
      | total_market_value_twd |
      | total_market_value_usd |
      | total_pl_twd           |
      | total_pl_pct           |

  Scenario: Fallback exchange rate when unavailable
    Given the USD/TWD exchange rate is unavailable
    When I request GET /api/stocks/tw
    Then the system should use fallback rate 32.0
