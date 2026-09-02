-- $2102/$2103 hold the sound id playing on TIA voice 0 / voice 1 ($FF = free).
-- sub_DEF3 allocates by priority (dat_E1CB), sub_DED6 frees.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local F,p0,p1=0,0xFF,0xFF
local count={}
emu.register_frame_done(function()
  F=F+1
  local a,b=mem:read_u8(0x2102),mem:read_u8(0x2103)
  if a~=p0 and a~=0xFF then
    print(string.format("f%-6d voice0  sound $%02X",F,a)); count[a]=(count[a] or 0)+1 end
  if b~=p1 and b~=0xFF then
    print(string.format("f%-6d voice1  sound $%02X",F,b)); count[b]=(count[b] or 0)+1 end
  p0,p1=a,b
  if F>=11941 then
    print("\n=== totals ===")
    local k={} for id in pairs(count) do k[#k+1]=id end table.sort(k)
    for _,id in ipairs(k) do print(string.format("  $%02X started %d times",id,count[id])) end
    M:exit()
  end
end)
