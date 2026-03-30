# Karen Edge Cases — Nurse System (Tier 2)
#
# These scenarios cover the failure modes that don't show up in unit tests
# because they require the full command chain: app → platform → message broker
# → job system → device layer → deadbolt.
#
# These are the scenarios that were failing silently in production
# while the API tests were green.

Feature: Resident Access — Edge Cases and Command Chain Failures
  As a QA engineer protecting Karen
  I need to verify that the full command chain holds under realistic failure conditions
  So that a green API test doesn't mask a broken device layer

  # ---------------------------------------------------------------------------
  # COMMAND CHAIN INTEGRITY
  # ---------------------------------------------------------------------------

  Scenario: Unlock command reaches the door controller, not just the platform API
    Given an unlock command is issued via the app
    And the platform API returns HTTP 200
    When we inspect the door controller telemetry
    Then the controller received the unlock command
    And the deadbolt physically moved to the unlocked position
    And the controller acknowledged the command back to the platform

  Scenario: Platform API success does not mask a controller timeout
    Given an unlock command is issued via the app
    And the platform API returns HTTP 200
    But the door controller did not acknowledge the command within 5 seconds
    Then the platform raises a delivery failure event
    And the failure is visible in the audit log
    And Karen's app does not display "Door Unlocked" without controller confirmation

  Scenario: Job queue backlog does not silently delay access commands
    Given the access command job queue has a processing backlog of more than 30 seconds
    When Karen issues an unlock command
    Then the app displays a "Taking longer than expected" state after 5 seconds
    And Karen is not left staring at a spinner with no feedback
    And the command is processed in order without being dropped

  # ---------------------------------------------------------------------------
  # MESSAGE BROKER FAILURES
  # ---------------------------------------------------------------------------

  Scenario: Unlock command survives a message broker restart mid-delivery
    Given an unlock command has been enqueued
    And the message broker restarts before the command is delivered
    When the broker comes back online
    Then the command is re-delivered exactly once (no duplicates)
    And the door is not left in an indeterminate state

  Scenario: Duplicate unlock commands do not cause device state confusion
    Given two identical unlock commands are delivered to the controller within 1 second
    When the controller processes both
    Then the door unlocks once
    And only one access event is written to the audit log

  # ---------------------------------------------------------------------------
  # CREDENTIAL PROPAGATION
  # ---------------------------------------------------------------------------

  Scenario: A new credential is available on the controller within 60 seconds of issuance
    Given property management issues Karen a new credential via the admin portal
    When 60 seconds have elapsed
    Then the credential is active on the door controller
    And Karen can unlock using the new credential without a manual sync step

  Scenario: A revoked credential is inactive on the controller within 60 seconds
    Given Karen's credential is revoked via the admin portal
    When 60 seconds have elapsed
    Then the credential is no longer accepted by the door controller
    And the revocation is not dependent on Karen making an unlock attempt to trigger a sync

  Scenario: Credential propagation is not broken by a concurrent software deploy
    Given a software release is in progress on the platform
    And a credential issuance event fires during the deploy window
    When the deploy completes
    Then the credential propagation job was not dropped
    And the credential is active on the controller within 90 seconds of issuance

  # ---------------------------------------------------------------------------
  # FIRMWARE AND CONTROLLER STATE
  # ---------------------------------------------------------------------------

  Scenario: Door controller recovers to a known-good state after a firmware update
    Given a firmware update was pushed to the door controller
    When the controller reboots after the update
    Then the controller comes online within 120 seconds
    And all previously issued credentials remain valid
    And the controller rejoins the property platform without manual intervention

  Scenario: A controller that loses power does not permanently lock residents out
    Given the door controller lost power unexpectedly
    When power is restored
    Then the controller reboots into a state that allows PIN-based access
    And the controller does not require a remote reset command to accept credentials
    And the power loss event is logged to the platform

  # ---------------------------------------------------------------------------
  # AUDIT TRAIL COMPLETENESS
  # ---------------------------------------------------------------------------

  Scenario Outline: Every access event type is captured in the audit log
    Given a <event_type> event occurs at the door
    Then an audit log entry is written within 10 seconds
    And the entry includes: timestamp, resident ID, door ID, event type, and result
    And the entry is queryable via the QA audit dashboard

    Examples:
      | event_type              |
      | successful app unlock   |
      | successful PIN unlock   |
      | failed credential       |
      | access denied (expired) |
      | emergency override used |
      | controller offline      |
      | credential revoked      |

  Scenario: Audit log entries are not lost during a platform failover
    Given a platform failover event occurs
    And 50 access events were recorded in the 60 seconds before failover
    When the platform recovers
    Then all 50 events are present in the audit log
    And no events have duplicate entries
    And the audit trail is contiguous with no time gaps

  # ---------------------------------------------------------------------------
  # REGRESSION CANARY — THESE SHOULD NEVER BREAK
  # ---------------------------------------------------------------------------

  Scenario: A new release does not change the unlock response time SLA
    Given the system is operating under normal load
    When Karen issues an unlock command via the app
    Then the door responds within 3 seconds
    And this SLA is validated as part of every release pipeline

  Scenario: A new release does not change the PIN unlock response time SLA
    Given the system is operating under normal load
    When Karen enters her PIN at the keypad
    Then the door responds within 2 seconds
    And this SLA is validated as part of every release pipeline
