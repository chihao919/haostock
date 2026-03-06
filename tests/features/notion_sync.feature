Feature: Notion as Single Source of Truth
  As a user
  I want all portfolio data to come from Notion
  So that I can manage positions in the Notion UI without touching code

  Scenario: Read US stock positions from Notion
    Given the Notion US Stocks database has 11 positions across 4 accounts
    When I request GET /api/stocks/us
    Then all 11 positions should be returned
    And positions should be grouped by account

  Scenario: Read TW stock positions from Notion
    Given the Notion TW Stocks database has positions with Chinese names
    When I request GET /api/stocks/tw
    Then each position should include the "name" field from Notion

  Scenario: Read options from Notion
    Given the Notion Options database has 12 active positions
    When I request GET /api/options
    Then all 12 options should be returned with current market data

  Scenario: Read bonds from Notion
    Given the Notion Bonds database has 5 bonds
    When I request GET /api/networth
    Then bond income calculations should use all 5 bonds

  Scenario: Read loans from Notion
    Given the Notion Loans database has 2 loans
    When I request GET /api/networth
    Then liability calculations should use all 2 loans

  Scenario: Adding a new position in Notion reflects in API
    Given I add a new position "AAPL" with 50 shares at avg_cost 180.00 to account "IBKR" in Notion
    When I request GET /api/stocks/us
    Then the response should include "AAPL" in account "IBKR"

  Scenario: Removing a position in Notion reflects in API
    Given I delete the position "GOOG" from account "Firstrade" in Notion
    When I request GET /api/stocks/us
    Then the response should not include "GOOG" in account "Firstrade"

  Scenario: Handle Notion API errors gracefully
    Given the Notion API returns a 500 error
    When I request GET /api/stocks/us
    Then the response status should be 502
    And the error message should indicate "Notion API unavailable"
