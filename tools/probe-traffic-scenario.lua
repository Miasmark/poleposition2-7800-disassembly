-- probe-traffic-scenario.lua -- a controlled two-player traffic run, no
-- recording. Boots, presses Select NAVN times on the title (NAV="Select"; 2
-- gives track 3, the busiest), starts, holds both accelerators, and once
-- driving pokes both speeds to a schedule PHASES="frames:p1speed:p2speed;..."
-- (laterals and the clock held; the clock must stay nonzero or player 2's
-- drive stops). Logs as probe-world.lua does (for tools/world-check.py), takes
-- screenshots at the drive-relative frames in SHOTS, and ends with a COST line:
-- RivalCars (entry RC, hex, default 4038) and the race tick's object tick in
-- scanlines, and the spacing of main-loop passes. env: O, FR.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local P=M.ioport.ports
local function fld(n) for _,t in ipairs({":buttons",":joysticks",":console_buttons"}) do local f=P[t].fields[n]; if f then return f end end end
local reset,b1,b2=fld("Reset"),fld("P1 Button 1"),fld("P2 Button 1")
local ph={} for a,b,c in string.gmatch(os.getenv("PHASES"),"(%d+):(%d+):(%d+)") do ph[#ph+1]={tonumber(a),tonumber(b),tonumber(c)} end
local o=io.open(os.getenv("O"),"w")
local f,drive0=0,nil; local lastT=-1
local function s16(a) local v=mem:read_u8(a)+256*mem:read_u8(a+1); if v>=32768 then v=v-65536 end return v end
local function want() if not drive0 then return nil end local t=f-drive0
  for _,p in ipairs(ph) do if t<p[1] then return p end t=t-p[1] end return nil end
TAPS={}
local LINE=1/(59.9224*262)
local RC=tonumber(os.getenv("RC") or "4038",16); local CT=tonumber(os.getenv("CT") or "0",16)
local rc0,ct0=nil,nil; local rcd,ctd,passes={}, {}, {}
TAPS[10]=mem:install_read_tap(RC,RC,"rc",function(a,v) if cpu.state["PC"].value==RC then rc0=M.time:as_double() end return v end)
TAPS[11]=mem:install_read_tap(0xD259,0xD259,"ps",function(a,v) if cpu.state["PC"].value==0xD259 and drive0 then passes[#passes+1]=f end return v end)
TAPS[12]=mem:install_read_tap(0xD710,0xD710,"ct",function(a,v) if cpu.state["PC"].value==0xD710 and ct0 then ctd[#ctd+1]=(M.time:as_double()-ct0)/LINE; ct0=nil end return v end)
TAPS[13]=mem:install_read_tap(0xD70D,0xD70D,"c0",function(a,v) if cpu.state["PC"].value==0xD70D then ct0=M.time:as_double() end return v end)
local function summary()
  local function q(t,p) table.sort(t); return t[math.max(1,math.floor(#t*p+0.5))] or 0 end
  local gaps={} for i=2,#passes do gaps[#gaps+1]=passes[i]-passes[i-1] end
  local h={} for _,g in ipairs(gaps) do h[g]=(h[g] or 0)+1 end
  local hs={} for k,v in pairs(h) do hs[#hs+1]=k..":"..v end table.sort(hs)
  return string.format("COST rivalcars n=%d med %.1f p90 %.1f max %.1f | object tick n=%d med %.1f p90 %.1f max %.1f | passes %d, frames between passes %s",
    #rcd,q(rcd,0.5),q(rcd,0.9),q(rcd,1.0),#ctd,q(ctd,0.5),q(ctd,0.9),q(ctd,1.0),#passes,table.concat(hs," "))
end
TAPS[1]=mem:install_read_tap(0xD719,0xD719,"w",function(a,v)
  if cpu.state["PC"].value==0xD719 then
    if rc0 then rcd[#rcd+1]=(M.time:as_double()-rc0)/LINE; rc0=nil end
    local st=mem:read_u8(0x9D)
    if st==2 or st==3 then
      local t=mem:read_u8(0xC4)
      if t~=lastT then lastT=t; local n=mem:read_u8(0xC2); local q={}
        for i=0,n-1 do q[#q+1]=string.format("%02X:%d",mem:read_u8(0x18B4+i),mem:read_u8(0x18D7+i)+256*mem:read_u8(0x195A+i)) end
        o:write("T "..t.." "..table.concat(q," ").."\n") end
      local ae=mem:read_u8(0xAE)
      o:write(string.format("f%d %02X %d gap=%d A0=%d A2=%d B0=%d B2=%d act=%d |",f,st,t,s16(0x275C),s16(0xA0),mem:read_u8(0xA2),s16(0x2792),mem:read_u8(0x2794),mem:read_u8(0x2791)))
      if ae<16 then for i=0,ae do local s=mem:read_u8(0x19A4+i)
        o:write(string.format(" %d:%02X:%d",s,mem:read_u8(0x19B4+s),mem:read_u8(0x19C4+s)+256*mem:read_u8(0x19D4+s))) end end
      o:write("\n")
    end
  end
  return v end)
emu.register_frame_done(function()
  f=f+1
  reset:set_value((f>=480 and f<490) and 1 or 0)
  local nav=os.getenv("NAV")
  if nav then local nf=fld(nav); local k=math.floor((f-300)/20); nf:set_value((f>=300 and k<tonumber(os.getenv("NAVN")) and (f-300)%20<6) and 1 or 0) end
  local st=mem:read_u8(0x9D)
  b1:set_value(f>=700 and 1 or 0); b2:set_value(f>=700 and 1 or 0)
  if not drive0 and st==2 then drive0=f end
  local p=want()
  if drive0 and os.getenv("SHOTS") then for w in string.gmatch(os.getenv("SHOTS"),"%d+") do if f-drive0==tonumber(w) then M.video:snapshot(); local v=mem:read_u8(0x275C)+256*mem:read_u8(0x275D); if v>=32768 then v=v-65536 end; o:write(string.format("SHOT f%d t%d gap=%d",f,f-drive0,v)..string.char(10)) end end end
  if p and st==2 then
    mem:write_u8(0xCE,p[2]); mem:write_u8(0x2753,p[3])
    mem:write_u8(0xD1,0xE0); mem:write_u8(0x2702,0x20)     -- player 1 a little left, player 2 the same side (P2_LATERAL + is left)
    mem:write_u8(0xDF,0x60); mem:write_u8(0xDE,0x00)       -- hold the clock (nonzero: player 2 drives only while it runs)
  end
  if f>=tonumber(os.getenv("FR")) or (drive0 and not p) then o:write(summary()..string.char(10)); o:close(); M:exit() end
end)
