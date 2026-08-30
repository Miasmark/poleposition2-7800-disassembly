-- Which addresses does MARIA actually fetch graphics from?
--
-- The 16,805-byte block at $8000 is the cartridge's biggest unknown. Guessing
-- at it with a renderer is the slow way round; the display list says where the
-- pixels come from, and it is built in RAM each frame. Walk the live DLL,
-- decode every entry, and report the distinct graphics addresses and widths.
local M = (type(manager.machine)=="function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local dpph, dppl = 0, 0
local T = {}
T[1] = mem:install_write_tap(0x2C, 0x2C, "h", function(o,d) dpph=d return d end)
T[2] = mem:install_write_tap(0x30, 0x30, "l", function(o,d) dppl=d return d end)
local F = 0
local AT = tonumber(os.getenv("AT") or "3000")
emu.register_frame_done(function()
  F = F + 1
  if F ~= AT then return end
  local addr = dpph*256 + dppl
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
      if (e1 & 0x1F) == 0 then
        ghi = mem:read_u8(dl + i + 2)
        w = 32 - (mem:read_u8(dl + i + 3) & 0x1F); i = i + 5
      else
        ghi = mem:read_u8(dl + i + 2)
        w = 32 - (e1 & 0x1F); i = i + 4
      end
      parts[#parts+1] = string.format("$%02X%02X/w%d", ghi, glo, w)
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
