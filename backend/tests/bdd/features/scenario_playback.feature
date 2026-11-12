Feature: Scenario playback controls
  Loading a scenario must leave the simulation paused at t=0 with scripted
  operations scheduled but not yet executed. Play advances time at the
  configured speed so mesh formation is visible. Reset restores a clean
  initial state ready to play again.

  Scenario: Load leaves simulation paused at t=0 ready to play
    Given the basic-mesh scenario is loaded for playback
    Then simulation time is 0
    And the simulation mode is "paused"
    And no scripted join or text events have executed yet
    And scripted operations are scheduled on the engine

  Scenario: Play at 1x executes scripted events progressively
    Given the basic-mesh scenario is loaded for playback
    When the simulation advances at 1x through the script horizon plus settle
    Then scripted joins and the text payload have executed
    And the forwarding group for "demo" is nodes 1 and 3
    And nodes 3 and 5 have delivered "ODMRP works"
    And simulation time is greater than 1

  Scenario: Reset restores clean initial state at t=0
    Given the basic-mesh scenario is loaded for playback
    And the simulation advances at 1x through the script horizon plus settle
    When the scenario is reset for playback
    Then simulation time is 0
    And the simulation mode is "paused"
    And no scripted join or text events have executed yet
    And scripted operations are scheduled on the engine
    And the simulation is ready to play again
