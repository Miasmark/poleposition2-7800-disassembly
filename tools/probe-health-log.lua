-- probe-health-log.lua -- one CSV line per frame for tools/health.py: frame,
-- InputAccel,InputBrake,PlayerX,LateralVel,RoadCurve,Speed,Gear,Clock,ClockHi.
-- Env: FRAMES (default 4200). Output goes to stdout; keep the lines that start
-- with a digit (see tools/check-build.sh).
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
local LIMIT = tonumber(os.getenv("FRAMES") or "4200")
emu.register_frame_done(function()
  F = F + 1
  print(string.format("%06d,%02X,%02X,%02X,%02X,%02X,%02X,%02X,%02X,%02X",
    F, mem:read_u8(0x00D7), mem:read_u8(0x00D8), mem:read_u8(0x00D1),
    mem:read_u8(0x00D0), mem:read_u8(0x00DA), mem:read_u8(0x00CE),
    mem:read_u8(0x00DB), mem:read_u8(0x00DF), mem:read_u8(0x00DE)))
  if F >= LIMIT then M:exit() end
end)
