-- probe-wild-fetch.lua -- the first CPU instruction fetch in $8000-$BFFF (graphics,
-- no code): frame, registers and 24 stack bytes (the return chain). Env: O, END.
-- first CPU instruction fetch in $8000-$BFFF (graphics): dump state and stack
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]; local mem=cpu.spaces["program"]
local f=0; local done=false; local o=io.open(os.getenv("O"),"w")
local ring={}
WT={}
WT[1]=mem:install_read_tap(0x8000,0xBFFF,"wild",function(a,d)
  if not done and cpu.state["PC"].value==a then
    done=true
    local sp=cpu.state["SP"].value
    o:write(string.format("f%d wild fetch at %04X A=%02X X=%02X Y=%02X SP=%02X P=%02X st=%02X\n",f,a,cpu.state["A"].value,cpu.state["X"].value,cpu.state["Y"].value,sp&0xFF,cpu.state["P"].value,mem:read_u8(0x9D)))
    local t={} for i=1,24 do t[#t+1]=string.format("%02X",mem:read_u8(0x100+((sp+i)&0xFF))) end
    o:write("stack: "..table.concat(t," ").."\n")
    o:write("recent frames: "..table.concat(ring," ").."\n")
    o:flush()
  end
  return d end)
emu.register_frame_done(function() f=f+1
  ring[#ring+1]=string.format("%d:%02X",f,mem:read_u8(0x9D)) if #ring>6 then table.remove(ring,1) end
  if f>=tonumber(os.getenv("END")) or (done and f>0) then o:close() M:exit() end end)
