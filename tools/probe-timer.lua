-- Find the race clock.
--
-- First attempt looked for a byte that only ever decreases. Zero candidates,
-- and the reason is in the manual: the allowance resets every lap (75 seconds
-- for the first, 60 after), so the clock rises sharply several times a run.
-- What it does instead is decrement far more often than it increments.
--
-- Sample once a second, count both directions, and report bytes that fall
-- steadily and rise only a handful of times.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local LO, HI = 0x1800, 0x27FF
local F, prev, dec, inc, first = 0, {}, {}, {}, {}
local END = tonumber(os.getenv("END") or "11942")

emu.register_frame_done(function()
  F = F + 1
  if F % 60 ~= 0 then return end
  for a = LO, HI do
    local v = mem:read_u8(a)
    if prev[a] == nil then
      prev[a] = v; dec[a] = 0; inc[a] = 0; first[a] = v
    else
      if v < prev[a] then dec[a] = dec[a] + 1
      elseif v > prev[a] then inc[a] = inc[a] + 1 end
      prev[a] = v
    end
  end
  if F >= END then
    local rows = {}
    for a = LO, HI do
      if dec[a] >= 20 and inc[a] <= 8 then
        rows[#rows+1] = {a, dec[a], inc[a], first[a], prev[a]}
      end
    end
    table.sort(rows, function(p, q) return (p[2]-p[3]) > (q[2]-q[3]) end)
    print("=== falls steadily, rises rarely (a clock that resets each lap) ===")
    for i = 1, math.min(#rows, 20) do
      local r = rows[i]
      print(string.format("  $%04X  %3d down / %2d up   started %3d, ended %3d",
            r[1], r[2], r[3], r[4], r[5]))
    end
    print(string.format("  %d candidates", #rows))
    M:exit()
  end
end)
