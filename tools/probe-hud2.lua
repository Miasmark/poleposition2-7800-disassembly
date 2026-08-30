-- Sharper filters. The first pass matched the road perspective tables, which
-- both reach $FF and duplicate themselves, so the shapes have to describe what
-- these values ARE rather than merely how they move.
--
--   speed   a physical quantity: it changes SMOOTHLY. Acceleration is gradual,
--           so frame-to-frame deltas are tiny even though the range is wide.
--           A graphics ramp rebuilt each frame jumps arbitrarily.
--   score   displayed, so BCD: every nibble 0-9, always. And it changes only
--           on scoring events, not every frame.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local LO, HI = 0x1800, 0x27FF
local F = 0
local prev, mx, mn, big, moves = {}, {}, {}, {}, {}
local SAMPLES = {6000, 7500, 9000, 10400}
local snaps = {}

local function bcd(v) return (v & 0x0F) <= 9 and ((v >> 4) & 0x0F) <= 9 end

emu.register_frame_done(function()
  F = F + 1
  if F > 4000 and F <= 10400 then
    for a = LO, HI do
      local v = mem:read_u8(a)
      if prev[a] == nil then mx[a]=v; mn[a]=v; big[a]=0; moves[a]=0
      else
        if v > mx[a] then mx[a]=v end
        if v < mn[a] then mn[a]=v end
        local d = v - prev[a]; if d < 0 then d = -d end
        if d > 3 then big[a] = big[a] + 1 end
        if v ~= prev[a] then moves[a] = moves[a] + 1 end
      end
      prev[a] = v
    end
  end
  for i,f in ipairs(SAMPLES) do
    if F == f then local s={} for a=LO,HI do s[a]=mem:read_u8(a) end snaps[i]=s end
  end
  if F == 10400 then
    print("=== smooth, wide-ranging bytes (speed) ===")
    local n=0
    for a = LO, HI do
      if mx[a] >= 0xF0 and mn[a] <= 0x10 and moves[a] > 300 and big[a] < 40 then
        n=n+1
        if n<=10 then print(string.format("  $%04X  $%02X-$%02X, moved %d, jumped %d",
              a, mn[a], mx[a], moves[a], big[a])) end
      end
    end
    print(string.format("  %d candidates", n))

    print("=== BCD 3-byte runs mirrored elsewhere, changing rarely ===")
    local hits=0
    for a = LO, HI-2 do
      local ok, moved = true, false
      for i=1,#SAMPLES do
        for k=0,2 do if not bcd(snaps[i][a+k]) then ok=false end end
      end
      if ok then
        for k=0,2 do if snaps[#SAMPLES][a+k] ~= snaps[1][a+k] then moved=true end end
      end
      if ok and moved then
        for b = a+3, HI-2 do
          local same=true
          for i=1,#SAMPLES do for k=0,2 do
            if snaps[i][a+k] ~= snaps[i][b+k] then same=false break end end
            if not same then break end end
          if same then
            hits=hits+1
            if hits<=10 then print(string.format("  $%04X mirrors $%04X   %02X %02X %02X",
                  a, b, snaps[#SAMPLES][a], snaps[#SAMPLES][a+1], snaps[#SAMPLES][a+2])) end
          end
        end
      end
    end
    print(string.format("  %d pairs", hits))
    M:exit()
  end
end)
