-- zerotap.lua -- is anything ever read from these zero runs? CPU fetches and
-- MARIA DMA cross the same bus in MAME, so a read tap sees both.
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local out=os.getenv("Z_OUT") or "zerotap"
local stop=tonumber(os.getenv("Z_FRAMES") or "6000")
local runs={}
HIT={}
for line in io.lines(os.getenv("Z_RUNS")) do
  local a,b=line:match("(%d+) (%d+)")
  if a then runs[#runs+1]={tonumber(a),tonumber(b),0} end
end
TAPS={}
for i,r in ipairs(runs) do
  TAPS[i]=mem:install_read_tap(r[1],r[2],"z"..i,function(o,d) if F>=300 then HIT[o]=true end; return d end)
end
F=0
local f=0
emu.register_frame_done(function()
  f=f+1; F=f
  if f>=stop then
    local o=io.open(out..".txt","w")
    for a,_ in pairs(HIT) do o:write(a..string.char(10)) end
    o:close(); M:exit()
  end
end)
