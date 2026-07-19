# Collections — date reminders

## Why

Collections have date properties and the platform has a notification system, but
nothing connects them. A reminder that fires a notification when a row's date
arrives turns a collection into a real task tracker — the cheapest high-value
workflow to unlock, since both halves already exist.

## What Changes

- A date property MAY carry a reminder lead time (at the date, or N minutes/
  hours/days before). When a row's date (minus the lead) is reached, the system
  notifies the row's creator once, via the existing notification dispatcher.
- A scheduled sweep (postgres deployment, like the email digest) finds due
  reminders and dispatches them, recording that a given row/property/date value
  was reminded so it never fires twice; changing the date re-arms it.

## Impact

- Affected specs: `collections`.
- Affected code: domain (`PropertyDef.reminder_minutes`), a reminder-sweep use
  case, a reminder-state repository (in-memory + postgres) + migration, wiring +
  a scheduler loop + settings; frontend date-property reminder control. Reuses
  the notification dispatcher — no new channel.
