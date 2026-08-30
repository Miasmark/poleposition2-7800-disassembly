-- No filtering: log every write to the speed byte, through both mirror views,
-- across one crash. The value reaches zero without any write OF zero, so the
-- question is what the writes actually look like.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local cpu=M.devices[":maincpu"]
local F,TAPS,n=0,{},0
local function watch(lo,tag)
  TAPS[#TAPS+1]=mem:install_write_tap(lo,lo,"sp",function(off,data)
    if F>=7500 and F<=7545 and n<60 then
      n=n+1
      print(string.format("f%-6d  write %3d via $%04X  from PC $%04X",F,data,off,cpu.state["PC"].value))
    end
    return data
  end)
end
watch(0x00CE,"zp") watch(0x20CE,"mir")
emu.register_frame_done(function()
  F=F+1
  if F>=7000 and F<=7560 and F%10==0 then
    print(string.format("f%-6d  speed now %d",F,mem:read_u8(0xCE)))
  end
  if F>7560 then M:exit() end
end)
