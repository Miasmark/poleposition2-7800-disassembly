-- Reliable event detection, derived from the collision code rather than taps.
--
--   sub_C86E ($C86E)  walks 16 object slots:
--       $19B4,X  flags; low 3 bits = type
--       $19C4/$19D4,X  16-bit Z distance
--   L_C907 ($C907)  on contact, branches on that type:
--       type 2      -> SpeedDecay ($C92F)  speed -= speed/8
--       otherwise   -> L_C93E              crash: $D3 = slot, $D4 = $20 timer
--
-- SpeedDecay has exactly two xrefs, both inside that block, so a drop of
-- precisely speed>>3 IS a type-2 contact.  Ambiguous only when speed>>3 == 16
-- (speed 128..135), where it cannot be told from the flat -16 at $D6EE.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local SPEED,CRASH,TIMER=0x00CE,0x00D3,0x00D4
local TYPE,ZLO,ZHI=0x19B4,0x19C4,0x19D4
local F,ps,pd3=0,0,0xFF

local function slots()          -- active objects, nearest first
  local t={}
  for x=0,15 do
    local z=mem:read_u8(ZHI+x)*256+mem:read_u8(ZLO+x)
    local ty=mem:read_u8(TYPE+x)%8
    if z<0x2000 then t[#t+1]={x=x,ty=ty,z=z} end
  end
  table.sort(t,function(a,b) return a.z<b.z end)
  local s={}
  for i=1,math.min(#t,4) do s[#s+1]=string.format("[%X]t%d z%d",t[i].x,t[i].ty,t[i].z) end
  return table.concat(s," ")
end

emu.register_frame_done(function()
  F=F+1
  local s=mem:read_u8(SPEED)
  local d3=mem:read_u8(CRASH)
  if d3~=0xFF and pd3==0xFF then
    print(string.format("f%-6d CRASH   slot %02X  type %d  speed %3d  timer %d",
          F, d3, mem:read_u8(TYPE+d3)%8, s, mem:read_u8(TIMER)))
    print("                "..slots())
  end
  if s~=ps then
    local dec=ps-(ps>>3)
    if s==dec and ps>0 then
      print(string.format("f%-6d DECAY   %3d -> %3d  (-%d)   %s",F,ps,s,ps-s,slots()))
    elseif s==ps-16 then
      print(string.format("f%-6d FLAT16  %3d -> %3d",F,ps,s))
    elseif s==0 and ps>16 then
      print(string.format("f%-6d ZERO    %3d -> 0",F,ps))
    end
  end
  ps,pd3=s,d3
  if F>=11941 then M:exit() end
end)
