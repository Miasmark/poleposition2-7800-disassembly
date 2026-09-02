-- $C4 is the track index sub_D917 loads from; $C1/$C2 are the two stream lengths.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local F,seen=0,{}
emu.register_frame_done(function()
  F=F+1
  if F>3000 and F%600==0 then
    local k=string.format("track $%02X  lenA %d  lenB %d",mem:read_u8(0xC4),mem:read_u8(0xC1),mem:read_u8(0xC2))
    if not seen[k] then seen[k]=F; print(string.format("f%-6d %s",F,k)) end
  end
  if F>=11000 then M:exit() end
end)
