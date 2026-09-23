-- probe-collide-scenario.lua -- no recording; both players scripted: PHASES "len:s1:s2:x1:lat2:hold;..."
-- (speeds poked every frame; laterals set every frame when hold=1, once at the
-- phase start when 0). Boots, presses Select NAVN times (2 = track 3), starts,
-- holds both accelerators; pokes apply in qualifying and the race (puddles are
-- only laid for the race). O: every contact -- player 1's CrashStart
-- (rom:C93E) and SpeedDecay (rom:C92F), player 2's (env P2C, P2P), with the
-- caller (ret $F605 = player 2's sign, from its segment counter). O2: every
-- lateral test, as probe-contact-tests.lua (env CUR, ABS, PUD, CRS). TRACE=1
-- logs both laterals each frame. Was: Logs every contact: player 1's CrashStart (rom:C93E)
-- and SpeedDecay (rom:C92F), player 2's P2CrashStart / P2Puddle (env P2C, P2P).
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local P=M.ioport.ports
local function fld(n) for _,t in ipairs({":buttons",":joysticks",":console_buttons"}) do local f=P[t].fields[n]; if f then return f end end end
local reset,b1,b2,sel=fld("Reset"),fld("P1 Button 1"),fld("P2 Button 1"),fld("Select")
local ph={} for a,b,c,d,e,g in string.gmatch(os.getenv("PHASES"),"(%d+):(%d+):(%d+):(%-?%d+):(%-?%d+):(%d)") do ph[#ph+1]={tonumber(a),tonumber(b),tonumber(c),tonumber(d),tonumber(e),tonumber(g)} end
local o=io.open(os.getenv("O"),"w")
local f,drive0=0,nil; local lastph=nil
local function s16(a) local v=mem:read_u8(a)+256*mem:read_u8(a+1); if v>=32768 then v=v-65536 end return v end
local function s8(v) if v>=128 then return v-256 end return v end
local function want() if not drive0 then return nil end local t=f-drive0
  for i,p in ipairs(ph) do if t<p[1] then return p,i end t=t-p[1] end return nil end
local function ev(name,slot)
  local sp=cpu.state["SP"].value
  local ret=mem:read_u8(0x100+((sp+1)&0xFF))+256*mem:read_u8(0x100+((sp+2)&0xFF))
  local ty=slot and mem:read_u8(0x19B4+slot) or 0
  o:write(string.format("%s f%d gap=%d x1=%d x2=%d slot=%s type=%02X z1=%s ret=%04X spd1=%d spd2=%d\n",name,f,s16(0x275C),s8(mem:read_u8(0xD1)),-s8(mem:read_u8(0x2702)),
    slot and tostring(slot) or "-",ty,slot and tostring(s16(0x19C4+slot) and (mem:read_u8(0x19C4+slot)+256*mem:read_u8(0x19D4+slot))) or "-",ret,mem:read_u8(0xCE),mem:read_u8(0x2753)))
end
local P2C,P2P=tonumber(os.getenv("P2C"),16),tonumber(os.getenv("P2P"),16)
TAPS={}
TAPS[1]=mem:install_read_tap(0xC93E,0xC93E,"a",function(a,v) if cpu.state["PC"].value==0xC93E then ev("P1CRASH",cpu.state["X"].value) end return v end)
TAPS[2]=mem:install_read_tap(0xC92F,0xC92F,"b",function(a,v) if cpu.state["PC"].value==0xC92F then ev("P1PUDDLE",mem:read_u8(0xB3)) end return v end)
TAPS[3]=mem:install_read_tap(P2C,P2C,"c",function(a,v) if cpu.state["PC"].value==P2C then ev("P2CRASH",mem:read_u8(0x27BC)) end return v end)
TAPS[4]=mem:install_read_tap(P2P,P2P,"d",function(a,v) if cpu.state["PC"].value==P2P then ev("P2PUDDLE",mem:read_u8(0x27BC)) end return v end)
local o2=io.open(os.getenv("O2"),"w")
CURV=nil
local CU=tonumber(os.getenv("CUR"),16)
TAPS[30]=mem:install_read_tap(CU,CU,"cu",function(a,v) if cpu.state["PC"].value==CU then CURV=mem:read_u8(0x1A31+mem:read_u8(0x27BD)) end return v end)
local cur=nil
local ABS,PUD,CRS=tonumber(os.getenv("ABS"),16),tonumber(os.getenv("PUD"),16),tonumber(os.getenv("CRS"),16)
local function pc() return cpu.state["PC"].value end
TAPS[10+1]=mem:install_read_tap(0xC8C1,0xC8C1,"a",function(a,v) if pc()==0xC8C1 then
  local x=cpu.state["X"].value; local y=cpu.state["Y"].value
  cur=string.format("P1 f%d slot=%d type=%02X z=%d lane=%d row=%d curve=%d px=%d m4e=%d",f,x,mem:read_u8(0x19B4+x),mem:read_u8(0x19C4+x)+256*mem:read_u8(0x19D4+x),
    mem:read_u8(0x1A00+x),y,mem:read_u8(0x1A31+y),mem:read_u8(0xD1),mem:read_u8(0x4E)) end return v end)
TAPS[10+2]=mem:install_read_tap(0xC8DE,0xC8DE,"b",function(a,v) if pc()==0xC8DE and cur then o2:write(cur..string.format(" abs=%d\n",cpu.state["A"].value)); cur=nil end return v end)
TAPS[10+3]=mem:install_read_tap(0xC907,0xC907,"c",function(a,v) if pc()==0xC907 then o2:write(string.format("P1HIT f%d slot=%d\n",f,mem:read_u8(0xB3))) end return v end)
TAPS[10+4]=mem:install_read_tap(ABS,ABS,"d",function(a,v) if pc()==ABS then local x=mem:read_u8(0x27BC)
  o2:write(string.format("P2 f%d slot=%d type=%02X zl=%d zh=%d lane=%d m=%d lat=%d curve=%d abs=%d\n",f,x,mem:read_u8(0x19B4+x),mem:read_u8(0x27B8),mem:read_u8(0x27B9),mem:read_u8(0x1A00+x),mem:read_u8(0x271F),(256-mem:read_u8(0x27BE))%256,(CURV or 0),cpu.state["A"].value)) end return v end)
TAPS[10+5]=mem:install_read_tap(PUD,PUD,"e",function(a,v) if pc()==PUD then o2:write(string.format("P2HIT f%d slot=%d\n",f,mem:read_u8(0x27BC))) end return v end)
TAPS[10+6]=mem:install_read_tap(CRS,CRS,"g",function(a,v) if pc()==CRS then o2:write(string.format("P2HIT f%d slot=%d\n",f,mem:read_u8(0x27BC))) end return v end)

emu.register_frame_done(function()
  f=f+1
  reset:set_value((f>=480 and f<490) and 1 or 0)
  local nav=tonumber(os.getenv("NAVN") or "0"); local k=math.floor((f-300)/20)
  sel:set_value((f>=300 and k<nav and (f-300)%20<6) and 1 or 0)
  b1:set_value(f>=700 and 1 or 0); b2:set_value(f>=700 and 1 or 0)
  local st=mem:read_u8(0x9D)
  if not drive0 and st==2 then drive0=f end
  if os.getenv("RACEONLY") and st~=3 then return end
  local p,i=want()
  if p and (st==2 or st==3) then
    mem:write_u8(0xCE,p[2]); mem:write_u8(0x2753,p[3])
    if p[6]==1 or i~=lastph then mem:write_u8(0xD1,p[4]&0xFF); mem:write_u8(0x2702,p[5]&0xFF) end
    mem:write_u8(0xDF,0x60); mem:write_u8(0xDE,0x00)
    if i~=lastph then o:write(string.format("PHASE %d f%d\n",i,f)); lastph=i end
    if os.getenv("TRACE") then o:write(string.format("T f%d x1=%d x2=%d gap=%d cr1=%d cr2=%d\n",f,s8(mem:read_u8(0xD1)),-s8(mem:read_u8(0x2702)),s16(0x275C),mem:read_u8(0xD4),mem:read_u8(0x27B5))) end
  end
  if f>=tonumber(os.getenv("FR")) or (drive0 and not p) then o:close(); o2:close(); M:exit() end
end)
