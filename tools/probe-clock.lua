-- Watch the timer candidate and its neighbours, to see the shape of the clock:
-- where it starts, how fast it falls, and what it resets to.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
local last = nil
local END = tonumber(os.getenv("END") or "11942")
emu.register_frame_done(function()
  F = F + 1
  if F % 30 ~= 0 then return end
  local v = {}
  for a = 0xDC, 0xE2 do v[#v+1] = string.format("%02X", mem:read_u8(a)) end
  local line = table.concat(v, " ")
  if line ~= last then
    print(string.format("f%-6d  $DC-$E2: %s   ($DF=%d dec)", F, line, mem:read_u8(0xDF)))
    last = line
  end
  if F >= END then M:exit() end
end)
