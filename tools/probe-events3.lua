-- Same detector, but dump every OCCUPIED object slot (type ~= 0) at each event,
-- nearest first.  Fields per sub_C86E:
--   $19B4,X type/flags   $19C4+$19D4,X  16-bit Z   $1A00,X and $1A2E,X lateral
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local SPEED,CRASH=0x00CE,0x00D3
local TYPE,ZLO,ZHI,LAT,OFS=0x19B4,0x19C4,0x19D4,0x1A00,0x1A2E
local F,ps,pd3=0,0,0xFF

local function dump(why)
  local t={}
  for x=0,15 do
    local f=mem:read_u8(TYPE+x)
    if f~=0 then
      t[#t+1]={x=x,ty=f%8,f=f,z=mem:read_u8(ZHI+x)*256+mem:read_u8(ZLO+x),
               lat=mem:read_u8(LAT+x),ofs=mem:read_u8(OFS+x)}
    end
  end
  table.sort(t,function(a,b) return a.z<b.z end)
  local s={}
  for _,o in ipairs(t) do
    s[#s+1]=string.format("%X:t%d/%02X z%5d x%3d/%3d",o.x,o.ty,o.f,o.z,o.lat,o.ofs)
  end
  print(string.format("        player x=$%02X  %s",mem:read_u8(0x00D1),table.concat(s,"  ")))
end

emu.register_frame_done(function()
  F=F+1
  local s,d3=mem:read_u8(SPEED),mem:read_u8(CRASH)
  if d3~=0xFF and pd3==0xFF then
    print(string.format("f%-6d CRASH  slot %02X type %d speed %d",F,d3,mem:read_u8(TYPE+d3)%8,s)); dump()
  end
  if s~=ps and s==ps-(ps>>3) and ps>0 then
    print(string.format("f%-6d DECAY  %d -> %d",F,ps,s)); dump()
  end
  ps,pd3=s,d3
  if F>=11060 then M:exit() end
end)
