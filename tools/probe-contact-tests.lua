-- probe-contact-tests.lua -- every lateral contact test, both players, with its
-- inputs and outcome, for tools/contact-model-check.py.
-- P1: rom:C8C1 (row found; X slot, Y row), rom:C8DE (A = |value|), rom:C907 (contact)
-- P2: P2ClCurve (the curve byte as used), P2ClAbs (A = |value|), P2Puddle /
-- P2CrashStart (contact). env CUR, ABS, PUD, CRS (hex, from splitscreen._ext()), O, FR.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local o=io.open(os.getenv("O"),"w"); local f=0
local cur=nil
CURV=nil
local ABS,PUD,CRS=tonumber(os.getenv("ABS"),16),tonumber(os.getenv("PUD"),16),tonumber(os.getenv("CRS"),16)
local function pc() return cpu.state["PC"].value end
TAPS={}
local CU=tonumber(os.getenv("CUR"),16)
TAPS[30]=mem:install_read_tap(CU,CU,"cu",function(a,v) if cpu.state["PC"].value==CU then CURV=mem:read_u8(0x1A31+mem:read_u8(0x27BD)) end return v end)
TAPS[1]=mem:install_read_tap(0xC8C1,0xC8C1,"a",function(a,v) if pc()==0xC8C1 then
  local x=cpu.state["X"].value; local y=cpu.state["Y"].value
  cur=string.format("P1 f%d slot=%d type=%02X z=%d lane=%d row=%d curve=%d px=%d m4e=%d",f,x,mem:read_u8(0x19B4+x),mem:read_u8(0x19C4+x)+256*mem:read_u8(0x19D4+x),
    mem:read_u8(0x1A00+x),y,mem:read_u8(0x1A31+y),mem:read_u8(0xD1),mem:read_u8(0x4E)) end return v end)
TAPS[2]=mem:install_read_tap(0xC8DE,0xC8DE,"b",function(a,v) if pc()==0xC8DE and cur then o:write(cur..string.format(" abs=%d\n",cpu.state["A"].value)); cur=nil end return v end)
TAPS[3]=mem:install_read_tap(0xC907,0xC907,"c",function(a,v) if pc()==0xC907 then o:write(string.format("P1HIT f%d slot=%d\n",f,mem:read_u8(0xB3))) end return v end)
TAPS[4]=mem:install_read_tap(ABS,ABS,"d",function(a,v) if pc()==ABS then local x=mem:read_u8(0x27BC)
  o:write(string.format("P2 f%d slot=%d type=%02X zl=%d zh=%d lane=%d m=%d lat=%d curve=%d abs=%d\n",f,x,mem:read_u8(0x19B4+x),mem:read_u8(0x27B8),mem:read_u8(0x27B9),mem:read_u8(0x1A00+x),mem:read_u8(0x271F),(256-mem:read_u8(0x27BE))%256,(CURV or 0),cpu.state["A"].value)) end return v end)
TAPS[5]=mem:install_read_tap(PUD,PUD,"e",function(a,v) if pc()==PUD then o:write(string.format("P2HIT f%d slot=%d\n",f,mem:read_u8(0x27BC))) end return v end)
TAPS[6]=mem:install_read_tap(CRS,CRS,"g",function(a,v) if pc()==CRS then o:write(string.format("P2HIT f%d slot=%d\n",f,mem:read_u8(0x27BC))) end return v end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then o:close(); M:exit() end end)
