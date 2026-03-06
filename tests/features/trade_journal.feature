Feature: Trade Journal
  As an investor
  I want to record my trade history with reasons and lessons learned
  So that I can review my trading decisions and improve over time

  # --- Recording Trades ---

  Scenario: Record a winning stock trade
    When I POST /api/trades with:
      | field        | value                              |
      | date         | 2026-03-06                         |
      | ticker       | NVDA                               |
      | action       | Sell                                |
      | asset_type   | Stock                              |
      | qty          | 50                                  |
      | price        | 250.00                              |
      | total_amount | 12500.00                            |
      | pl           | 3287.00                             |
      | result       | Win                                 |
      | reason       | 目標價到達，技術面出現頂部背離       |
      | lesson       | 分批出場比一次全出更好，留一半繼續跑 |
      | tags         | Momentum, Technical                 |
      | account      | IBKR                                |
    Then the response status should be 201
    And the trade should be created in the Notion Trades database

  Scenario: Record a losing option trade
    When I POST /api/trades with:
      | field        | value                                  |
      | date         | 2026-03-06                             |
      | ticker       | MU                                      |
      | action       | Close                                   |
      | asset_type   | Option                                  |
      | qty          | 1                                       |
      | price        | 22.00                                   |
      | total_amount | 2200.00                                 |
      | pl           | -400.00                                 |
      | result       | Loss                                    |
      | reason       | 賣 call 被穿，MU 財報超預期大漲         |
      | lesson       | 財報前不要賣裸 call，至少做 spread 控風險 |
      | tags         | Earnings Play, Naked Call                |
      | account      | Firstrade                                |
    Then the response status should be 201

  Scenario: Record a trade with minimal fields
    When I POST /api/trades with:
      | field        | value          |
      | date         | 2026-03-06     |
      | ticker       | CCJ            |
      | action       | Buy            |
      | asset_type   | Stock          |
      | qty          | 100            |
      | price        | 95.00          |
      | total_amount | 9500.00        |
      | reason       | 鈾礦長期看多   |
      | account      | Firstrade      |
    Then the response status should be 201
    And the trade should have "result" as null
    And the trade should have "pl" as null
    And the trade should have "lesson" as null

  # --- Validation ---

  Scenario: Reject trade without required fields
    When I POST /api/trades without "ticker"
    Then the response status should be 422

  Scenario: Reject invalid action type
    When I POST /api/trades with action "InvalidAction"
    Then the response status should be 422

  Scenario: Reject invalid result type
    When I POST /api/trades with result "Maybe"
    Then the response status should be 422

  # --- Querying Trades ---

  Scenario: Query all trades with default limit
    Given there are 60 trades in the Notion Trades database
    When I request GET /api/trades
    Then the response should contain 50 trades
    And trades should be sorted by date descending

  Scenario: Filter trades by ticker
    Given there are trades for "CCJ", "NVDA", and "GOOG"
    When I request GET /api/trades?ticker=CCJ
    Then all returned trades should have ticker "CCJ"

  Scenario: Filter trades by result
    Given there are 18 wins and 5 losses
    When I request GET /api/trades?result=Win
    Then all returned trades should have result "Win"

  Scenario: Filter trades by asset type
    Given there are stock trades and option trades
    When I request GET /api/trades?asset_type=Option
    Then all returned trades should have asset_type "Option"

  Scenario: Custom limit
    When I request GET /api/trades?limit=10
    Then the response should contain at most 10 trades

  # --- Trade Summary Statistics ---

  Scenario: Calculate win rate
    Given the trade history contains:
      | result     | count |
      | Win        | 18    |
      | Loss       | 5     |
      | Breakeven  | 2     |
    When I request GET /api/trades
    Then the summary should show:
      | field        | value  |
      | total_trades | 25     |
      | wins         | 18     |
      | losses       | 5      |
      | breakeven    | 2      |
      | win_rate     | 72.0   |

  Scenario: Calculate average win and loss
    Given winning trades have P&L: 500, 800, 1200
    And losing trades have P&L: -200, -400
    When I request GET /api/trades
    Then the summary should show:
      | field            | value    |
      | avg_win          | 833.33   |
      | avg_loss         | -300.00  |
      | total_realized_pl| 1900.00  |

  # --- Integration with Portfolio ---

  Scenario: Claude reviews trade history for patterns
    Given I have recorded 50+ trades over 3 months
    When Claude queries GET /api/trades
    Then Claude can analyze:
      - Win rate trends over time
      - Most profitable tickers
      - Common reasons for losses
      - Whether lessons learned are being applied
