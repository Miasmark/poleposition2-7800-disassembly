-- coltest.lua -- both players scripted: PHASES "len:s1:s2:x1:lat2:hold;..."
-- (speeds poked every frame; laterals set every frame when hold=1, once at the
-- phase start when 0). Logs every contact: player 1's CrashStart (rom:C93E)
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
SNAPAT={}
local function ev(name,slot)
  if os.getenv("AUTOSNAP") then for w in string.gmatch(os.getenv("AUTOSNAP"),"%d+") do SNAPAT[f+tonumber(w)]=name end end
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
local function hx(a,n) local t={} for i=0,n-1 do t[#t+1]=string.format("%02X",mem:read_u8(a+i)) end return table.concat(t) end
local lastst=-1
local qd=false
emu.register_frame_done(function() local st=mem:read_u8(0x9D)
 if st==0x12 and not qd then qd=true; o:write(string.format("QT f%d A6=%d qst=%d qpos=%d p1lap=%02X.%02X p2lap=%02X.%02X p2qsec=%02X p2lapc=%02X p1out=%d",f,mem:read_u8(0xA6),mem:read_u8(0x26FC),mem:read_u8(0x26FD),mem:read_u8(0xBD),mem:read_u8(0xBC),mem:read_u8(0x2774),0,mem:read_u8(0x26FE),mem:read_u8(0x26FF),mem:read_u8(0x2736))..string.char(10)) end end)
local rd=false
emu.register_frame_done(function() if mem:read_u8(0x9D)==0x03 and not rd then rd=true; o:write(string.format("RACE f%d p1out=%d A6=%d qpos=%d park=%d",f,mem:read_u8(0x2736),mem:read_u8(0xA6),mem:read_u8(0x26FD),mem:read_u8(0x2700))..string.char(10)) end end)
emu.register_frame_done(function()
  f=f+1
  local stq=mem:read_u8(0x9D)
  if f%60==0 or stq~=lastst then lastst=stq
    o:write(string.format("V f%d st=%02X p1score=%s p2score=%s p1lap=%02X%02X.%02X p2lap=%02X%02X run=%d clock=%02X gap=%d A6=%d qst=%d qpos=%d park=%d x1=%d x2=%d | C3=%d A7=%d p2clk=%02X%02X p2lapn=%d rst=%d race=%d",f,stq,hx(0x1CA5,3),hx(0x2770,3),mem:read_u8(0xBE),mem:read_u8(0xBD),mem:read_u8(0xBC),mem:read_u8(0x2775),mem:read_u8(0x2774),mem:read_u8(0x2776),mem:read_u8(0xDF),s16(0x275C),mem:read_u8(0xA6),mem:read_u8(0x26FC),mem:read_u8(0x26FD),mem:read_u8(0x2700),(function(v) if v>127 then return v-256 end return v end)(mem:read_u8(0xD1)),-(function(v) if v>127 then return v-256 end return v end)(mem:read_u8(0x2702)),mem:read_u8(0xC3),mem:read_u8(0xA7),mem:read_u8(0x2730),mem:read_u8(0x2731),mem:read_u8(0x2733),mem:read_u8(0x2734),mem:read_u8(0x2735))..string.char(10)) end
  if SNAPAT[f] then M.video:snapshot(); o:write(string.format("SNAP f%d after %s cr1=%d cr2=%d gap=%d",f,SNAPAT[f],mem:read_u8(0xD4),mem:read_u8(0x27B5),s16(0x275C))..string.char(10)) end
  if os.getenv("SNAPS") then for w in string.gmatch(os.getenv("SNAPS"),"%d+") do if f==tonumber(w) then M.video:snapshot(); o:write(string.format("SNAP f%d cr1=%d cr2=%d",f,mem:read_u8(0xD4),mem:read_u8(0x27B5))..string.char(10)) end end end
  reset:set_value((f>=480 and f<490) and 1 or 0)
  local nav=tonumber(os.getenv("NAVN") or "0"); local k=math.floor((f-300)/20)
  sel:set_value((f>=300 and k<nav and (f-300)%20<6) and 1 or 0)
  b1:set_value(f>=700 and 1 or 0); b2:set_value(f>=700 and 1 or 0)
  local st=mem:read_u8(0x9D)
  if not drive0 and st==2 then drive0=f end
  if os.getenv("RACEONLY") and st~=3 then return end
  local p,i=want()
  if p and (st==2 or st==3) then
    if not (os.getenv("FREECLK") and (st==3 or (os.getenv("FREECLK")=="2" and st==2)) and mem:read_u8(0xDE)==0 and mem:read_u8(0xDF)==0) then if mem:read_u8(0x2736)==0 then mem:write_u8(0xCE,p[2]) end end; if mem:read_u8(0x2734)==0 then mem:write_u8(0x2753,p[3]) end
    if p[6]==1 or i~=lastph then mem:write_u8(0xD1,p[4]&0xFF); mem:write_u8(0x2702,p[5]&0xFF) end
    if not (os.getenv("FREECLK") and (st==3 or (os.getenv("FREECLK")=="2" and st==2))) then mem:write_u8(0xDF,0x60); mem:write_u8(0xDE,0x00) end
    if i~=lastph then o:write(string.format("PHASE %d f%d\n",i,f)); lastph=i end
    if os.getenv("TRACE") then o:write(string.format("T f%d x1=%d x2=%d gap=%d cr1=%d cr2=%d\n",f,s8(mem:read_u8(0xD1)),-s8(mem:read_u8(0x2702)),s16(0x275C),mem:read_u8(0xD4),mem:read_u8(0x27B5))) end
  end
  if f>=tonumber(os.getenv("FR")) or (drive0 and not p) then o:close(); M:exit() end
end)
