-- Resolve the two indirect jumps --check-gaps flagged on day one:
--     rom:D26A   JMP ($0040)
--     rom:EC06   JMP ($00FD)
-- Their targets cannot be known statically. This watches the vectors as the
-- game runs and reports every distinct target each one is pointed at, with the
-- frame it first appeared, so they can go into annotations.json as ram_vectors.
--
-- Zero page $40/$FD are the mirror of $2040/$20FD; either view is the same RAM.
local M = (type(manager.machine) == "function") and manager:machine() or manager.machine
local mem = M.devices[":maincpu"].spaces["program"]
local F = 0
local seen = {}          -- "name:target" -> first frame
local order = {}
local VECS = { {name = "D26A JMP ($0040)", lo = 0x0040},
               {name = "EC06 JMP ($00FD)", lo = 0x00FD} }

emu.register_frame_done(function()
  F = F + 1
  for _, v in ipairs(VECS) do
    local t = mem:read_u8(v.lo) | (mem:read_u8(v.lo + 1) << 8)
    if t ~= 0 then
      local key = string.format("%s -> $%04X", v.name, t)
      if not seen[key] then seen[key] = F; order[#order + 1] = key end
    end
  end
  if F >= 17115 then
    print("=== targets each RAM vector was pointed at ===")
    for _, k in ipairs(order) do
      print(string.format("  %-26s first seen frame %d", k, seen[k]))
    end
    M:exit()
  end
end)
