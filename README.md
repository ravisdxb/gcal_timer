# gcal_timer
Repository for gcal_timer
----------------------------------------------
get oauth credentials from Google

add a helper input_boolean
Settings > Devices & Services > Helpers > Create Helper > Toggle
 Name: gcal_update
 Icon: mdi:calendar-clock (or something similar)

Install appdaemon (if not already done)
Settings > Add-onstore > AppDaemon (from Home Assistant Community Add-ons section)

config/appdaemon/apps.yaml (add to end)
gcal_timer:
  module: gcal_timer
  class: GCalTimer
  EVENTS_LIMIT: 15
  TRIGGER: input_boolean.gcal_update

Directories and Files:

config/appdaemon/apps
 gcal_timer.py (new)
 
config/appdaemon/gcal (new directory)
 credentials.json (new file downloaded from Google)

config/appdaemon/lib (new directory)
 entire contents of lib directory

config/www (new directory)
 entire contents of www directory
