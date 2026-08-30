-- Find the score, then watch the end-of-run tally.
--
-- The manual says 50 a car passed and 200 a second left, and run-02 ends with
-- the tally adding both before game over. So the score is a run of bytes that
-- never decreases, and during the tally its increments should be exact
-- multiples of those two values -- which is what turns the manual's numbers
-- from claims into findings.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local LO, HI = 0x1800, 0x27FF
local F, prev, alive, moves = 0, {}, {}, {}
local reported = false
local TALLY = tonumber(os.getenv("TALLY") or "10900")
local END = tonumber(os.getenv("END") or "11942")

emu.register_frame_done(function()
  F = F + 1
  if F % 30 ~= 0 then return end
  for a = LO, HI do
    local v = mem:read_u8(a)
    if prev[a] == nil then prev[a] = v; alive[a] = true; moves[a] = 0
    elseif alive[a] then
      if v < prev[a] then alive[a] = false
      elseif v > prev[a] then moves[a] = moves[a] + 1 end
      prev[a] = v
    end
  end
  if not reported and F >= TALLY then
    reported = true
    print("=== bytes that never decreased, by how often they rose ===")
    local rows = {}
    for a = LO, HI do
      if alive[a] and moves[a] >= 3 then rows[#rows+1] = {a, moves[a], prev[a]} end
    end
    table.sort(rows, function(p,q) return p[2] > q[2] end)
    for i = 1, math.min(#rows, 14) do
      print(string.format("  $%04X  rose %d times, now $%02X", rows[i][1], rows[i][2], rows[i][3]))
    end
    print(string.format("  %d candidates", #rows))
  end
  if F >= END then M:exit() end
end)
