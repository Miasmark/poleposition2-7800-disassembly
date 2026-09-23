-- pickshots.lua -- screenshot moments that test the lateral signs: the cars
-- close together on opposite sides of the road, and collisions.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local o=io.open(os.getenv("O"),"w")
local f,last,n=0,-999,0
local function sgn(v) if v>127 then return v-256 end return v end
emu.register_frame_done(function()
  f=f+1
  local st=mem:read_u8(0x9D)
  if (st==2 or st==3) and f-last>=90 and n<8 then
    local p1=sgn(mem:read_u8(0xD1)); local p2w=-sgn(mem:read_u8(0x2702))
    local gap=mem:read_u8(0x275C)+256*mem:read_u8(0x275D); if gap>=32768 then gap=gap-65536 end
    local hit=mem:read_u8(0x276D)
    local why=nil
    if math.abs(gap)<400 and p1*p2w<0 and math.abs(p1-p2w)>50 then why="opposite sides" end
    if hit==1 then why="collision" end
    if why then
      M.video:snapshot(); last=f; n=n+1
      o:write(string.format("shot %d f%d %s: P1 at %d, P2 at %d (player-1 terms, + is right), gap %d",n,f,why,p1,p2w,gap)..string.char(10))
    end
  end
  if f>=9000 then o:close(); M:exit() end
end)
