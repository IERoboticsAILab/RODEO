# One charging measurement, on /rodeo/charge in a charging proof. Measured by
# the charging station (e.g. WiBotic VMonBatt / IBattery / ChargeState), not
# by the robot.
builtin_interfaces/Time stamp
float32 voltage_v
float32 current_a
string state              # e.g. idle, ramp_up, cc, cv, full, alarm
