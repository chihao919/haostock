Feature: Net Worth Summary
  As an investor
  I want a complete net worth overview
  So that I can see my total assets, liabilities, and income at a glance

  Background:
    Given the USD/TWD exchange rate is 32.15
    And US stock positions total market value is 200000.00 USD
    And TW stock positions total market value is 20000000 TWD
    And bonds data from Notion:
      | name           | face   | coupon  | cost   |
      | UBS 5.699%     | 280000 | 0.05699 | 299040 |
      | BAC 5.468%     | 480000 | 0.05468 | 503400 |
    And loans data from Notion:
      | name     | balance  | monthly |
      | 房屋貸款 | 19600000 | 33078   |
      | 其他貸款 | 39450000 | 66579   |

  Scenario: Calculate total assets in USD
    When I request GET /api/networth
    Then assets should include:
      | field            | value      |
      | us_stocks_usd    | 200000.00  |
      | tw_stocks_usd    | 622084.14  |
      | bonds_cost_usd   | 802440     |

  Scenario: Calculate total liabilities
    When I request GET /api/networth
    Then liabilities should include:
      | field              | value       |
      | total_loans_twd    | 59050000    |
      | monthly_payments_twd | 99657     |

  Scenario: Convert loans TWD to USD
    When I request GET /api/networth
    Then "total_loans_usd" should equal total_loans_twd divided by usdtwd_rate

  Scenario: Calculate bond income with 30% withholding tax
    When I request GET /api/networth
    Then bonds_annual_net_usd should be 70% of bonds_annual_gross_usd
    And bonds_monthly_net_usd should be bonds_annual_net_usd divided by 12

  Scenario: Net worth = assets - liabilities
    When I request GET /api/networth
    Then net_worth_usd should equal total_assets_usd minus total_loans_usd
    And net_worth_twd should equal net_worth_usd multiplied by usdtwd_rate

  Scenario: Response includes exchange rate
    When I request GET /api/networth
    Then the response should contain "usdtwd_rate"
