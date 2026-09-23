-- drive.lua -- drive both players from a script, no recording: a list of
-- "frame:field,field,..." steps held until the next step. Logs state, both
-- speeds, both laterals (player 1's terms) and B8 each frame.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local P=M.ioport.ports
local function fld(name)
  for _,t in ipairs({":buttons",":joysticks",":console_buttons"}) do
    local f=P[t].fields[name]; if f then return f end
  end
  error("no field "..name)
end
local steps={}
for step in string.gmatch(os.getenv("SCRIPT"),"[^;]+") do
  local fr,list=step:match("(%d+):(.*)")
  local names={}
  for n in string.gmatch(list,"[^,]+") do names[#names+1]=n end
  steps[#steps+1]={tonumber(fr),names}
end
local all={}
for _,s in ipairs(steps) do for _,n in ipairs(s[2]) do all[n]=fld(n) end end
local o=io.open(os.getenv("O"),"w")
o:write("f,state,b8,p1spd,p2spd,p1x,p2x,p1gear,p2gear,p1curve,p2curve,crash,inputs,clock"..string.char(10))
local f=0
local function sgn(v) if v>127 then return v-256 end return v end
emu.register_frame_done(function()
  f=f+1
  local cur={}
  for _,s in ipairs(steps) do if f>=s[1] then cur=s[2] end end
  local on={} for _,n in ipairs(cur) do on[n]=true end
  for n,fl in pairs(all) do fl:set_value(on[n] and 1 or 0) end
  o:write(string.format("%d,%02X,%d,%d,%d,%d,%d,%02X,%02X",f,mem:read_u8(0x9D),mem:read_u8(0xB8),
    mem:read_u8(0xCE),mem:read_u8(0x2753),sgn(mem:read_u8(0xD1)),-sgn(mem:read_u8(0x2702)),
    mem:read_u8(0xDB),mem:read_u8(0x270E))..string.format(",%d,%d,%d,%s",
    sgn(mem:read_u8(0x1900+mem:read_u8(0xCF))),sgn(mem:read_u8(0x1900+mem:read_u8(0x2750))),mem:read_u8(0xD4),
    table.concat(cur,"+"))..string.format(",%d",mem:read_u8(0xDE)*256+mem:read_u8(0xDF))..string.char(10))
  if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end
end)
