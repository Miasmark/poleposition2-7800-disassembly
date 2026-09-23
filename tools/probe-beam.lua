-- beam.lua -- where is the beam when the main loop's 10 Hz work runs?
-- MAME's screen object has no vpos here, so the beam is derived from emulated
-- time, anchored to vblank start: the instant the BIT MSTAT/BPL spin at $DB8E
-- falls through to its RTS at $DB92, which is when VBLANK goes high.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local out=os.getenv("B_OUT") or "beam"
local LINE=1/(59.9224*262)
local f=0
local vb=nil
local rows={}
local function now() return M.time:as_double() end
local SITES={ [0xDB92]="VBLANK", [0xEA2C]="stage copy begins", [0xE70D]="object rebuild begins", [0xE713]="object rebuild done" }
TAPS={}
local i=0
for pc,name in pairs(SITES) do
  i=i+1
  TAPS[i]=mem:install_read_tap(pc,pc,"b"..i,function(o,d)
    if cpu.state["PC"].value==pc then
      local t=now()
      if name=="VBLANK" then vb=t
      elseif f>=1400 and f<=3600 and vb then
        rows[#rows+1]=string.format("%s,%.2f",name,(t-vb)/LINE)
      end
    end
    return d end)
end
emu.register_frame_done(function()
  f=f+1
  if f>3600 then
    local o=io.open(out..".csv","w")
    for _,r in ipairs(rows) do o:write(r..string.char(10)) end
    o:close(); M:exit()
  end
end)
