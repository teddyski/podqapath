# Karen Scenarios — Nurse System (Tier 2)
#
# Karen is an ICU nurse. She just worked a 13-hour shift.
# Her phone is at 13%. She is standing at her front door.
# She does not care what changed in your sprint.
# She cares that her door opens.
#
# These are Tier 2 scenarios. Tier 2 = locks, access control, resident safety.
# Any code change that could affect these scenarios requires human sign-off.
# QA-7 will block release if Tier 2 regression is unverified.
#
# Tier reference:
#   Tier 0 — UI / cosmetic (dashboard displays, labels, styles)
#   Tier 1 — Non-safety device behavior (lighting, notifications, parking)
#   Tier 2 — Access control, locks, HVAC/temperature, resident safety (THIS FILE)
#
# Why HVAC is Tier 2:
#   Moscow, 2010. Thousands of residents died during an extreme heatwave in buildings
#   where cooling failed. The inverse is equally true — heating failure in winter is
#   a hypothermia risk. Karen just worked a 13-hour ICU shift. She is already depleted.
#   A broken thermostat is not an inconvenience. It is a medical event waiting to happen.

Feature: Resident Door Access — Tier 2 Safety
  As Karen, a resident returning home after a 13-hour ICU shift
  I need to access my apartment reliably under degraded conditions
  So that I am never stranded at my own door because of a software change

  Background:
    Given Karen has a valid active lease
    And Karen has an authorized credential (mobile app, PIN, or key fob)
    And the door controller firmware is current

  # ---------------------------------------------------------------------------
  # HAPPY PATH
  # ---------------------------------------------------------------------------

  Scenario: Karen unlocks her front door via the mobile app
    Given the property platform is online
    And Karen opens the resident app
    When she taps "Unlock" on her home unit
    Then the door unlocks within 3 seconds
    And the app displays "Door Unlocked"
    And the access event is written to the audit log with a timestamp

  Scenario: Karen unlocks her door using the keypad PIN
    Given the property platform is online
    When Karen enters her 6-digit PIN at the door keypad
    Then the door unlocks within 2 seconds
    And the access event is written to the audit log

  # ---------------------------------------------------------------------------
  # LOW BATTERY / DEGRADED DEVICE
  # ---------------------------------------------------------------------------

  Scenario: Karen unlocks her door when her phone is below 15% battery
    Given Karen's phone battery is at 13%
    And low power mode is active
    When she attempts to unlock via the app
    Then the unlock command is sent without prompting for re-authentication
    And the door responds within 5 seconds
    And no additional step is required due to device battery state

  Scenario: Karen's cached app credential works when the phone has no data connection
    Given Karen's phone has no cellular or WiFi connectivity
    And the app has a locally cached valid credential
    When Karen opens the app and taps "Unlock"
    Then the app attempts a local Bluetooth unlock if the controller supports it
    And Karen is not shown an error without also being shown a fallback option

  # ---------------------------------------------------------------------------
  # NETWORK DEGRADATION
  # ---------------------------------------------------------------------------

  Scenario: Karen unlocks her door when building WiFi is experiencing packet loss
    Given the building network is experiencing packet loss above 20%
    When Karen attempts to unlock via the app
    Then the unlock command is retried automatically up to 3 times
    And the door unlocks within 10 seconds
    Or the app presents the PIN fallback option with clear instructions

  Scenario: Karen uses her PIN when the property platform is fully offline
    Given the property management platform is unreachable
    And Karen's PIN is stored locally on the door controller
    When Karen enters her PIN at the keypad
    Then the door unlocks immediately without platform confirmation
    And the access event is queued locally for sync when connectivity restores

  # ---------------------------------------------------------------------------
  # POST-RELEASE CONTINUITY
  # ---------------------------------------------------------------------------

  Scenario: Karen's access is unaffected after a production release
    Given a software release was deployed within the last 24 hours
    And Karen held an active credential before the release
    When Karen attempts to unlock her door
    Then the door unlocks normally
    And no re-enrollment, re-authentication, or cache-busting is triggered
    And Karen's access history and credential remain intact

  Scenario: Karen's access survives a backend database migration
    Given a database migration ran during the last maintenance window
    And Karen's credential record existed before the migration
    When Karen attempts to unlock her door the next morning
    Then her credential is valid
    And her access history is preserved and queryable

  # ---------------------------------------------------------------------------
  # ACCESS REVOCATION
  # ---------------------------------------------------------------------------

  Scenario: Karen's access is revoked promptly when her lease ends
    Given Karen's lease end date is today at 23:59
    And the lease expiry job has executed
    When Karen attempts to unlock her door after midnight
    Then the door does not unlock
    And Karen receives a clear in-app notification that her access has expired
    And the denial event is written to the audit log with the revocation reason

  Scenario: Karen's access is revoked immediately when security flags her credential
    Given a security event has flagged Karen's credential for suspension
    When Karen attempts to unlock her door
    Then access is denied immediately regardless of cached state
    And the denial is logged with the flagging event reference
    And Karen is notified through the app within 60 seconds

  # ---------------------------------------------------------------------------
  # FAILURE MODES — SILENT FAILURES ARE NOT ACCEPTABLE
  # ---------------------------------------------------------------------------

  Scenario: Karen is not silently locked out when her credential expires
    Given Karen's app credential has expired server-side
    And the app has not notified Karen of the expiry
    When Karen taps "Unlock"
    Then the app does not show a generic error
    And Karen receives a specific message explaining the credential state
    And a path to resolve the issue (re-auth or contact management) is shown

  Scenario: Karen is not silently locked out after 3 failed unlock attempts
    Given Karen's app is presenting a stale credential
    When Karen taps "Unlock" 3 times consecutively without success
    Then the system does not continue failing silently
    And Karen receives a notification after the second failure
    And a support contact option is available within the app

  Scenario: Unlock failure is observable in the audit log
    Given an unlock attempt fails for any reason
    Then a failure event is written to the audit log
    And the log entry includes: timestamp, credential ID, failure reason, and door controller ID
    And the failure is surfaced in QA-7's release audit if it occurred within the release window

  # ---------------------------------------------------------------------------
  # HVAC / TEMPERATURE CONTROL — TIER 2
  # Moscow 2010: extreme heat events kill residents. HVAC failure is not Tier 1.
  # ---------------------------------------------------------------------------

  Scenario: Karen's apartment maintains temperature after a software release
    Given a software release was deployed within the last 24 hours
    And Karen's thermostat was set to a temperature before the release
    When Karen returns home
    Then the thermostat setpoint is unchanged
    And the HVAC system is operating normally
    And no re-configuration is required after the release

  Scenario: Karen's thermostat responds to a setpoint change within acceptable time
    Given Karen is home and adjusts the thermostat setpoint
    When she submits the change via the app or thermostat unit
    Then the HVAC system responds within 60 seconds
    And the app reflects the updated setpoint
    And the change is logged to the device audit trail

  Scenario: HVAC failure is surfaced to the resident, not silently ignored
    Given the HVAC system has stopped responding to commands
    When more than 15 minutes have elapsed without acknowledgment
    Then Karen receives an in-app notification that the system is unresponsive
    And a support contact option is presented
    And the failure event is logged with timestamp and device ID

  Scenario: Temperature control works during a platform outage
    Given the property management platform is offline
    And Karen's thermostat has a locally stored schedule
    When the platform is unreachable
    Then the thermostat continues executing its schedule independently
    And the HVAC system remains operational without a cloud connection
    And setpoint changes made locally on the thermostat unit take effect immediately

  Scenario: HVAC setpoint is not reset to a default after a firmware update
    Given the thermostat firmware was updated overnight
    And Karen had a setpoint of 72°F configured before the update
    When Karen wakes up
    Then the setpoint is still 72°F
    And the HVAC is not running at a factory default temperature
    And Karen's schedule and preferences are intact

  # ---------------------------------------------------------------------------
  # EMERGENCY ACCESS
  # ---------------------------------------------------------------------------

  Scenario: Karen requires emergency access when all credentials fail
    Given Karen's app credential has expired
    And her PIN is not working
    And no key fob is available
    When Karen contacts the property emergency support line
    Then staff can issue a temporary override PIN within 5 minutes
    And the override is valid for a single use or 24 hours, whichever comes first
    And the override is logged with the issuing staff member's ID and timestamp
    And the override expires automatically — it cannot be left permanently active
