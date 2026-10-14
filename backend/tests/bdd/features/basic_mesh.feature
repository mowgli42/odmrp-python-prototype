Feature: Basic mesh formation
  Scenario: Source with data originates first Join Query and receivers get the payload
    Given the basic-mesh scenario is loaded
    When the simulation settles
    Then the forwarding group for "demo" is nodes 1 and 3
    And nodes 3 and 5 have delivered "ODMRP works"
