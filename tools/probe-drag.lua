-- Can the car accelerate on the verge?  $D7 bit7 clear = accelerator held
-- (sub_C17E stores the inverted controller read).  $DB is the gear.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local function sx(v) return v>127 and v-256 or v end
local F,ps=0,0
-- buckets: [onroad/verge][throttle held] -> {up, down, same, sumdelta}
local B={}
for _,z in ipairs{"road","verge"} do B[z]={} for _,t in ipairs{"gas","off"} do B[z][t]={u=0,d=0,s=0,n=0} end end
emu.register_frame_done(function()
  F=F+1
  local s=mem:read_u8(0xCE)
  if F>3200 and F<10900 and mem:read_u8(0xD4)==0 and mem:read_u8(0xD3)==0xFF then          -- the race proper, after qualifying
    local a=math.abs(sx(mem:read_u8(0xD1)))
    local z = a>=60 and "verge" or "road"
    local t = (mem:read_u8(0xD7)<0x80) and "gas" or "off"
    local b=B[z][t]
    if s>ps then b.u=b.u+1 elseif s<ps then b.d=b.d+1 else b.s=b.s+1 end
    b.n=b.n+1
  end
  ps=s
  if F>=10900 then
    for _,z in ipairs{"road","verge"} do for _,t in ipairs{"gas","off"} do
      local b=B[z][t]
      if b.n>0 then print(string.format("%-5s %-3s  %5d frames   rose %5d (%4.1f%%)  fell %5d  held %5d",
        z,t,b.n,b.u,100*b.u/b.n,b.d,b.s)) end
    end end
    M:exit()
  end
end)
