Feature: Financial Analysis
  As a user
  I want to analyze stock fundamentals (TW and US)
  So that I can evaluate stocks using Huang Kuo-Hua method and basic fundamental analysis

  # --- Taiwan Stock Analysis ---

  Scenario: Analyze a Taiwan stock with strong fundamentals
    Given FinMind returns revenue data showing 20% YoY growth for 2 consecutive months
    And FinMind returns balance sheet with CR=400%, QR=300%, Cash/TA=15%
    And FinMind returns income statements with NPM=20% and ROE=40%
    And FinMind returns positive and growing OCF
    And FinMind returns asset turnover of 1.2
    When I request GET /api/financial/analyze/2330
    Then the response status should be 200
    And the market should be "TW"
    And the method should be "Huang Kuo-Hua"
    And the score should be "5/5"
    And overall_pass should be true

  Scenario: Analyze a Taiwan stock with weak fundamentals
    Given FinMind returns revenue data showing 5% YoY growth
    And FinMind returns balance sheet with CR=150%, QR=100%, Cash/TA=5%
    When I request GET /api/financial/analyze/9999
    Then the response should have overall_pass false

  # --- US Stock Analysis ---

  Scenario: Analyze a US stock with strong fundamentals
    Given yfinance returns info with 35% revenue growth, 25% NPM, 35% ROE
    And yfinance returns positive OCF of $5B and FCF of $4B
    And yfinance returns current ratio of 300%
    When I request GET /api/financial/analyze/NVDA
    Then the response status should be 200
    And the market should be "US"
    And the score should be "4/4"
    And overall_pass should be true

  Scenario: Analyze a US stock with weak profitability
    Given yfinance returns info with 5% revenue growth, 1% NPM, 10% ROE
    When I request GET /api/financial/analyze/WEAK
    Then the response should have overall_pass false

  # --- Auto-detection ---

  Scenario: Numeric ticker routes to TW analysis
    When I request GET /api/financial/analyze/2330
    Then the market should be "TW"

  Scenario: Alpha ticker routes to US analysis
    When I request GET /api/financial/analyze/AAPL
    Then the market should be "US"

  # --- Valuation ---

  Scenario: TW stock returns EPS and target price
    Given FinMind returns EPS of 20.0 TTM and average PE of 25
    When I request GET /api/financial/analyze/2330
    Then the valuation should contain estimated_eps and target_price

  Scenario: US stock returns PE and forward PE
    Given yfinance returns PE of 30.0 and forward PE of 25.0
    When I request GET /api/financial/analyze/NVDA
    Then the valuation should contain pe_ratio and forward_pe
