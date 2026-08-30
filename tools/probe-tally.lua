-- Watch every RAM byte through the end-of-run tally.
--
-- A monotonic filter cannot find a BCD score: the low byte goes 98, 99, 00 on
-- carry, which is a decrease, so the test throws away the digits and keeps the
-- top byte alone. Instead, snapshot RAM before the tally and after it, and
-- report what moved -- a score shows up as a short run of adjacent bytes.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local LO, HI = 0x1800, 0x27FF
local F, before = 0, nil
local A = tonumber(os.getenv("A") or "10800")
local B = tonumber(os.getenv("B") or "11900")
emu.register_frame_done(function()
  F = F + 1
  if F == A then
    before = {}
    for a = LO, HI do before[a] = mem:read_u8(a) end
    print(string.format("snapshot taken at frame %d", A))
  elseif F == B and before then
    print(string.format("=== bytes that changed between frame %d and %d ===", A, B))
    local runs, cur = {}, nil
    for a = LO, HI do
      local v = mem:read_u8(a)
      if v ~= before[a] then
        if cur and a == cur.hi + 1 then cur.hi = a
        else cur = {lo=a, hi=a}; runs[#runs+1] = cur end
      end
    end
    for _, r in ipairs(runs) do
      if r.hi - r.lo >= 1 then
        local b, aft = {}, {}
        for a = r.lo, r.hi do
          b[#b+1] = string.format("%02X", before[a])
          aft[#aft+1] = string.format("%02X", mem:read_u8(a))
        end
        print(string.format("  $%04X-$%04X   %s  ->  %s", r.lo, r.hi,
              table.concat(b, " "), table.concat(aft, " ")))
      end
    end
    print(string.format("  %d runs of two or more adjacent bytes", #runs))
    M:exit()
  end
end)
