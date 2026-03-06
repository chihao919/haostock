Feature: US Stock Portfolio
  As an investor
  I want to query my US stock positions with real-time prices
  So that I can see my current P&L across all brokerage accounts

  Background:
    Given the Notion US Stocks database contains the following positions:
      | account   | ticker | shares | avg_cost |
      | Firstrade | NVDA   | 100    | 185.26   |
      | Firstrade | GOOG   | 200    | 307.61   |
      | IBKR      | VOO    | 3.19   | 627.38   |

  Scenario: Calculate P&L for a profitable position
    Given the current price of "NVDA" is 250.00
    When I request GET /api/stocks/us
    Then the response status should be 200
    And the position "NVDA" in account "Firstrade" should have:
      | field          | value     |
      | market_value   | 25000.00  |
      | cost_basis     | 18526.00  |
      | unrealized_pl  | 6474.00   |
      | pl_pct         | 34.95     |

  Scenario: Calculate P&L for a losing position
    Given the current price of "GOOG" is 280.00
    When I request GET /api/stocks/us
    Then the position "GOOG" in account "Firstrade" should have:
      | field          | value      |
      | market_value   | 56000.00   |
      | cost_basis     | 61522.00   |
      | unrealized_pl  | -5522.00   |
      | pl_pct         | -8.98      |

  Scenario: Aggregate totals per account
    Given the current price of "NVDA" is 250.00
    And the current price of "GOOG" is 280.00
    When I request GET /api/stocks/us
    Then account "Firstrade" should have:
      | field              | value    |
      | total_market_value | 81000.00 |
      | total_cost_basis   | 80048.00 |

  Scenario: Grand summary across all accounts
    Given all stock prices are fetched successfully
    When I request GET /api/stocks/us
    Then the response should contain a "summary" with:
      | field              |
      | total_market_value |
      | total_cost_basis   |
      | total_pl           |
      | total_pl_pct       |

  Scenario: Handle unavailable price gracefully
    Given the price of "NVDA" is unavailable
    When I request GET /api/stocks/us
    Then the position "NVDA" should have "current_price" as null
    And the position "NVDA" should not have "market_value"
    And the account totals should exclude "NVDA" from calculations

  Scenario: Price caching within a single request
    Given "NVDA" appears in multiple accounts
    When I request GET /api/stocks/us
    Then yfinance should be called only once for "NVDA"
