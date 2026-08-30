-- Which addresses does MARIA actually fetch graphics from?
--
-- The 16,805-byte block at $8000 is the cartridge's biggest unknown. Guessing
-- at it with a renderer is the slow way round; the display list says where the
-- pixels come from, and it is built in RAM each frame. Walk the live DLL,
-- decode every entry, and report the distinct graphics addresses and widths.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
-- DO NOT tap DPPH/DPPL to learn the address. Those taps catch the BIOS's
-- writes and stop firing before the cartridge makes its own, which yields
-- $1F84 -- the BIOS's display list -- and a screenful of nonsense that looks
-- like a decode failure. The game sets its own at $D89B and $D8D6; pass the
-- address in.
local DLLADDR = tonumber(os.getenv("DLL") or "0x2200")
local F = 0
local AT = tonumber(os.getenv("AT") or "3000")
emu.register_frame_done(function()
  F = F + 1
  if F ~= AT then return end
  local addr = DLLADDR
  print(string.format("DLL at $%04X", addr))
  local lines = 0
  for z = 0, 31 do
    local b0 = mem:read_u8(addr + z*3)
    local hi = mem:read_u8(addr + z*3 + 1)
    local lo = mem:read_u8(addr + z*3 + 2)
    local n  = (b0 & 0x0F) + 1
    local dl = (hi << 8) | lo
    local parts = {}
    local i = 0
    while i < 60 do
      local e1 = mem:read_u8(dl + i + 1)
      if e1 == 0 then break end
      local glo = mem:read_u8(dl + i)
      local w, ghi
      local x, raw
      if (e1 & 0x1F) == 0 then
        ghi = mem:read_u8(dl + i + 2)
        raw = mem:read_u8(dl + i + 3) & 0x1F
        w = 32 - raw; x = mem:read_u8(dl + i + 4); i = i + 5
      else
        ghi = mem:read_u8(dl + i + 2)
        raw = e1 & 0x1F
        w = 32 - raw; x = mem:read_u8(dl + i + 3); i = i + 4
      end
      parts[#parts+1] = string.format("$%02X%02X/w%d/raw%d/x%d", ghi, glo, w, raw, x)
    end
    if #parts > 0 then
      print(string.format("  zone %2d  %2d lines  flags $%02X  %s",
            z, n, b0, table.concat(parts, " ")))
    end
    lines = lines + n
    if lines >= 250 then break end
  end
  M:exit()
end)
