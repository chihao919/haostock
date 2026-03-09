Feature: Happy Five Lines (樂活五線譜) Analysis
  As an investor
  I want to see five-line regression analysis for any stock
  So that I can identify buy/sell signals based on statistical bands

  # --- Core Calculation ---

  Scenario: Calculate five lines for a valid ticker
    Given historical prices for "VOO" over 3.5 years
    When I calculate the five lines
    Then I should get 5 line values: plus_2sigma, plus_1sigma, mean, minus_1sigma, minus_2sigma
    And plus_2sigma > plus_1sigma > mean > minus_1sigma > minus_2sigma
    And I should get the current price
    And I should get a signal

  Scenario: Signal is "強烈買入" when price is below minus_2sigma
    Given a current price below the minus_2sigma line
    When I determine the signal
    Then the signal should be "強烈買入"

  Scenario: Signal is "加碼買入" when price is between minus_2sigma and minus_1sigma
    Given a current price between minus_2sigma and minus_1sigma
    When I determine the signal
    Then the signal should be "加碼買入"

  Scenario: Signal is "中性" when price is between minus_1sigma and plus_1sigma
    Given a current price between minus_1sigma and plus_1sigma
    When I determine the signal
    Then the signal should be "中性"

  Scenario: Signal is "賣出" when price is between plus_1sigma and plus_2sigma
    Given a current price between plus_1sigma and plus_2sigma
    When I determine the signal
    Then the signal should be "賣出"

  Scenario: Signal is "強烈賣出" when price is above plus_2sigma
    Given a current price above the plus_2sigma line
    When I determine the signal
    Then the signal should be "強烈賣出"

  Scenario: Insufficient data raises error
    Given historical prices with only 10 data points
    When I calculate the five lines
    Then it should raise an error "Not enough data points"

  # --- API Endpoint ---

  Scenario: API returns five lines analysis
    Given the API is running
    When I request GET /api/fivelines/VOO
    Then the response status should be 200
    And the response should contain "ticker", "current_price", "lines", "signal"
    And the "lines" should have keys: plus_2sigma, plus_1sigma, mean, minus_1sigma, minus_2sigma

  Scenario: API supports custom period
    Given the API is running
    When I request GET /api/fivelines/0050.TW?years=1
    Then the response status should be 200
    And the data_period should span approximately 1 year

  Scenario: API returns history for charting
    Given the API is running
    When I request GET /api/fivelines/VOO?include_history=true
    Then the response should contain a "history" array
    And each history entry should have date, close, and all 5 line values

  Scenario: API returns 404 for invalid ticker
    Given the API is running
    When I request GET /api/fivelines/INVALIDXYZ
    Then the response status should be 404

  # --- Web Page ---

  Scenario: Five lines page loads
    Given the API is running
    When I request GET /fivelines
    Then the response should be an HTML page
    And the page should contain a ticker input field
    And the page should contain a period selector
    And the page should contain a chart area

  # --- Batch Scanning ---

  Scenario: Scan multiple tickers for buy signals
    Given a list of tickers ["0050.TW", "VOO", "2330.TW"]
    When I scan for five lines signals
    Then each result should contain ticker, current_price, signal
    And results with signal "強烈買入" or "加碼買入" should be highlighted
