Feature: Options Positions
  As an options trader
  I want to see my options positions with P&L and suggested actions
  So that I can manage expiring positions and take profits

  Background:
    Given the Notion Options database contains the following positions:
      | account   | ticker | expiry     | strike | type | qty | cost   |
      | Firstrade | CCJ    | 2026-03-13 | 110    | put  | -1  | 479.98 |
      | Firstrade | GOOG   | 2026-03-21 | 330    | call | -1  | 244.98 |

  # --- ITM/OTM Detection ---

  Scenario: Detect OTM put option
    Given the current price of "CCJ" is 120.00
    And today is "2026-03-06"
    When I request GET /api/options
    Then the option CCJ 110 put expiring 2026-03-13 should show "OTM $10.0"

  Scenario: Detect ITM put option
    Given the current price of "CCJ" is 105.00
    And today is "2026-03-06"
    When I request GET /api/options
    Then the option CCJ 110 put expiring 2026-03-13 should show "ITM $5.0"

  Scenario: Detect OTM call option
    Given the current price of "GOOG" is 320.00
    When I request GET /api/options
    Then the option GOOG 330 call expiring 2026-03-21 should show "OTM $10.0"

  Scenario: Detect ITM call option
    Given the current price of "GOOG" is 340.00
    When I request GET /api/options
    Then the option GOOG 330 call expiring 2026-03-21 should show "ITM $10.0"

  # --- DTE & Urgency ---

  Scenario: DTE calculation
    Given today is "2026-03-06"
    When I request GET /api/options
    Then the option CCJ 110 put expiring 2026-03-13 should have DTE 7

  Scenario Outline: Urgency level based on DTE
    Given today is "<today>"
    When I calculate urgency for expiry "2026-03-13"
    Then the urgency should be "<urgency>"

    Examples:
      | today      | urgency |
      | 2026-03-06 | red     |
      | 2026-03-01 | yellow  |
      | 2026-02-01 | green   |

  # --- Action Suggestions ---

  Scenario: Suggest "EXPIRED" when DTE is 0 or negative
    Given today is "2026-03-14"
    When I evaluate action for DTE 0, P&L% 50, status "OTM"
    Then the suggested action should be "EXPIRED"

  Scenario: Suggest "Let expire" for OTM near expiry
    Given today is "2026-03-10"
    When I evaluate action for DTE 3, P&L% 90, status "OTM"
    Then the suggested action should be "Let expire"

  Scenario: Suggest "Close/Roll URGENT" for ITM near expiry
    Given today is "2026-03-10"
    When I evaluate action for DTE 3, P&L% 20, status "ITM"
    Then the suggested action should be "Close/Roll URGENT"

  Scenario: Suggest "Close" when profit exceeds 75%
    When I evaluate action for DTE 30, P&L% 80, status "OTM"
    Then the suggested action should be "Close (75%+ profit)"

  Scenario: Suggest "Monitor" within 21 DTE
    When I evaluate action for DTE 15, P&L% 40, status "OTM"
    Then the suggested action should be "Monitor"

  Scenario: Suggest "Hold" for far-dated options
    When I evaluate action for DTE 45, P&L% 30, status "OTM"
    Then the suggested action should be "Hold"

  # --- P&L Calculation ---

  Scenario: Calculate options P&L for short position
    Given the option CCJ 110 put was sold for cost 479.98
    And the current option mid price is 1.20
    When I calculate the options P&L
    Then the unrealized P&L should be 359.98
    And the P&L percentage should be 75.0

  # --- Sorting & Summary ---

  Scenario: Options sorted by DTE ascending
    When I request GET /api/options
    Then positions should be sorted by DTE ascending

  Scenario: Options summary totals
    When I request GET /api/options
    Then the summary should include:
      | field                |
      | total_cost_basis     |
      | total_current_value  |
      | total_pl             |
      | total_pl_pct         |
