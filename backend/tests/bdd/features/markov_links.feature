Feature: Markov RF link model
  Scenarios may enable a nested Markov connected/disconnected process on
  geometric radio neighbors so Play can run longer under configurable churn.

  Scenario: Markov link model flaps geometric neighbors on an interval
    Given a two-node topology within radio range
    And a markov link model with interval 1 that always drops then restores
    When the simulation advances by 1 second
    Then the nodes are not neighbors
    When the simulation advances by 1 more second
    Then the nodes are neighbors again

  Scenario: markov-mesh scenario arms the link model at load
    Given the markov-mesh scenario is loaded
    Then a link_model sim event was emitted
    And a link_model scheduler tick is pending
