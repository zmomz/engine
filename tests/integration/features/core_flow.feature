Feature: Core Application Flow

  Scenario: Full Signal Flow for a New Position
    Given the execution pool has a free slot
    When a valid webhook for a new position is received
    Then a new PositionGroup is created with status "live"
    And the correct number of DCAOrders are created with status "open"

  Scenario: Risk Engine Offsets a Losing Position
    Given a losing PositionGroup that meets all risk criteria
    And two winning PositionGroups are active
    When the Risk Engine evaluation is triggered
    Then the losing PositionGroup is market-closed
    And the winning PositionGroups are partially market-closed to offset the loss
    And a RiskAction is recorded with the details of the offset

  Scenario: Queue Promotion for a New Position
    Given the execution pool is full
    When a new signal is received
    Then a QueuedSignal is created
    And when an existing position is closed to free up a slot
    Then the queued signal is promoted and a new PositionGroup is created

  Scenario: System Recovery After Restart
    Given a PositionGroup with open orders is active
    When the application is forcefully restarted
    Then the startup reconciliation logic correctly identifies the open orders
    And the OrderFillMonitor continues to monitor them
