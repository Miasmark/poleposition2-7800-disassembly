-- probe-rom-coverage.lua -- bitmap of cart bytes $4000-$FFFF read after the reset code (env FR, RC_OUT); run with -playback
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]; local f=0; TAPS={}
-- ROM coverage: every cart byte read (CPU and MARIA) once the cart's reset code has run
RARM=false; RHIT={}
TAPS[96]=mem:install_read_tap(0xD205,0xD205,"arm",function(o,d) if cpu.state["PC"].value==0xD205 then RARM=true end return d end)
TAPS[97]=mem:install_read_tap(0x4000,0xFFFF,"rc",function(o,d) if RARM then RHIT[o]=true end return d end)
emu.register_frame_done(function() if f==tonumber(os.getenv("FR"))-1 then local o6=io.open(os.getenv("RC_OUT"),"wb"); local t={}
  for a=0x4000,0xFFFF do t[#t+1]=RHIT[a] and "1" or "0" end o6:write(table.concat(t)) o6:close() end end)
emu.register_frame_done(function() f=f+1; if f>=tonumber(os.getenv("FR")) then M:exit() end end)
