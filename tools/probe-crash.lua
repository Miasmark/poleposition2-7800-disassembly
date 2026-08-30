-- What writes zero to the speed byte? That is the collision handler.
--
-- NOT via a debugger watchpoint: an action containing `g` resumes and
-- re-breaks immediately, so the debugger loops and the recording never plays.
-- A write tap is the right instrument, and it must hold its own reference or
-- it is garbage-collected (toolkit pitfall #1). Reading the PC is the
-- expensive part, so it happens only on the rare zero-write, never on the
-- per-frame speed updates.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local cpu=M.devices[":maincpu"]
-- Tap BOTH views. The 7800 mirrors $2040-$20FF down to $0040-$00FF, so speed
-- is reachable as $CE and as $20CE, and a tap on one address does not see
-- accesses through the other. Tapping only $00CE caught nothing at all while
-- the value demonstrably went to zero twice.
local F,seen,TAPS=0,{},{}
local function watch(lo)
  TAPS[#TAPS+1] = mem:install_write_tap(lo, lo, "speed", function(off, data)
    if data == 0 then
      local pc = cpu.state["PC"].value
      local k = string.format("%04X", pc)
      seen[k] = (seen[k] or 0) + 1
      if seen[k] <= 3 then
        print(string.format("f%-6d  speed zeroed from PC $%s (via $%04X)", F, k, off))
      end
    end
    return data
  end)
end
watch(0x00CE)
watch(0x20CE)
emu.register_frame_done(function()
  F=F+1
  if F>=11940 then
    print("=== writers of zero to speed ===")
    for k,v in pairs(seen) do print(string.format("  $%s   x%d", k, v)) end
    M:exit()
  end
end)
