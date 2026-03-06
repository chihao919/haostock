Feature: Single Stock Quote & FX Rate
  As a user
  I want to get real-time quotes for individual stocks and exchange rates
  So that I can quickly check any ticker price

  # --- Single Quote ---

  Scenario: Get a valid US stock quote
    Given yfinance returns price 250.00 for "NVDA"
    When I request GET /api/quote/NVDA
    Then the response status should be 200
    And the response should contain:
      | field  | value  |
      | ticker | NVDA   |
      | price  | 250.00 |

  Scenario: Ticker is case-insensitive
    When I request GET /api/quote/nvda
    Then the response should have ticker "NVDA"

  Scenario: Get a Taiwan stock quote
    Given yfinance returns price 900.00 for "2330.TW"
    When I request GET /api/quote/2330.TW
    Then the response should contain:
      | field  | value   |
      | ticker | 2330.TW |
      | price  | 900.00  |

  Scenario: Return 404 for invalid ticker
    Given yfinance returns no data for "INVALIDTICKER"
    When I request GET /api/quote/INVALIDTICKER
    Then the response status should be 404

  # --- FX Rate ---

  Scenario: Get USD/TWD exchange rate
    Given yfinance returns price 32.15 for "USDTWD=X"
    When I request GET /api/fx
    Then the response status should be 200
    And the response should contain "USDTWD" equal to 32.15

  Scenario: FX fallback when unavailable
    Given yfinance returns no data for "USDTWD=X"
    When I request GET /api/fx
    Then the response should contain "USDTWD" equal to 32.0

  # --- Health ---

  Scenario: Health check returns ok
    When I request GET /api/health
    Then the response status should be 200
    And the response should contain "status" equal to "ok"
    And the response should contain a valid "timestamp"
