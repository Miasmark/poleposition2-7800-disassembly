-- Establishes each recording's TRUE frame length up front, before any
-- other analysis -- the Galaga project's own hard-won lesson: never
-- trust an early/short exit threshold as "the recording's length"; let
-- MAME's own playback exhaust naturally against a generous cap instead.
local MACHINE = (type(manager.machine) == "function")
                and manager:machine() or manager.machine
local F = 0
emu.register_frame_done(function()
  F = F + 1
  if F % 50000 == 0 then print("progress frame "..F) end
  if F >= 600000 then MACHINE:exit() end
end)
