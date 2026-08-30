-- Find the HUD values, using the shapes the layout implies.
--
--   score / high score   two runs of bytes that hold the SAME value and move
--                        together whenever the score is the high score
--   speed                a single byte that reaches $FF and varies widely,
--                        since the display tops out at 255
--
-- Sample at several points in the race and keep only what holds at all of them.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local LO, HI = 0x1800, 0x27FF
local SAMPLES = {6000, 7000, 8000, 9000, 10000}
local F, snaps = 0, {}
local seenmax, seenmin, changes, prev = {}, {}, {}, {}

emu.register_frame_done(function()
  F = F + 1
  -- speed: track range and how often each byte moves, every frame
  if F > 4000 and F <= 10500 then
    for a = LO, HI do
      local v = mem:read_u8(a)
      if seenmax[a] == nil then seenmax[a] = v; seenmin[a] = v; changes[a] = 0
      else
        if v > seenmax[a] then seenmax[a] = v end
        if v < seenmin[a] then seenmin[a] = v end
        if prev[a] ~= nil and v ~= prev[a] then changes[a] = changes[a] + 1 end
      end
      prev[a] = v
    end
  end
  for i, f in ipairs(SAMPLES) do
    if F == f then
      local s = {}
      for a = LO, HI do s[a] = mem:read_u8(a) end
      snaps[i] = s
    end
  end
  if F == 10500 then
    print("=== bytes reaching $FF with a wide range (speed candidates) ===")
    local n = 0
    for a = LO, HI do
      if seenmax[a] == 0xFF and seenmin[a] <= 0x10 and changes[a] > 400 then
        n = n + 1
        if n <= 12 then
          print(string.format("  $%04X  range $%02X-$%02X, changed %d times",
                a, seenmin[a], seenmax[a], changes[a]))
        end
      end
    end
    print(string.format("  %d candidates", n))

    print("=== 3-byte runs duplicated elsewhere in RAM at every sample ===")
    local hits = 0
    for a = LO, HI - 2 do
      local moved = false
      for i = 2, #SAMPLES do
        if snaps[i] and snaps[1] then
          for k = 0, 2 do
            if snaps[i][a+k] ~= snaps[1][a+k] then moved = true end
          end
        end
      end
      if moved then
        for b = a + 3, HI - 2 do
          local same = true
          for i = 1, #SAMPLES do
            if not snaps[i] then same = false break end
            for k = 0, 2 do
              if snaps[i][a+k] ~= snaps[i][b+k] then same = false break end
            end
            if not same then break end
          end
          if same then
            hits = hits + 1
            if hits <= 10 then
              print(string.format("  $%04X mirrors $%04X   (now %02X %02X %02X)",
                    a, b, snaps[#SAMPLES][a], snaps[#SAMPLES][a+1], snaps[#SAMPLES][a+2]))
            end
          end
        end
      end
    end
    print(string.format("  %d mirrored pairs", hits))
    M:exit()
  end
end)
