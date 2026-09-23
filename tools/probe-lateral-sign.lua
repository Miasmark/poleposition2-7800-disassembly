-- p2sign.lua -- player 2's road x in its own view against P2_LATERAL, and
-- player 1's the same way, bucketed by lateral: which way does each road move?
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local RX=tonumber(os.getenv("RX"),16)
local f=0
local b1,b2={},{}
local function sgn(v) if v>127 then return v-256 end return v end
emu.register_frame_done(function()
  f=f+1
  local s=mem:read_u8(0x9D)
  if (s==2 or s==3) and f>1400 then
    local l2=sgn(mem:read_u8(0x2702)); local x2=sgn(mem:read_u8(RX))
    local l1=sgn(mem:read_u8(0xD1));  local x1=sgn(mem:read_u8(0x244C+3))
    local k2=math.floor(l2/16); b2[k2]=b2[k2] or {0,0}; b2[k2][1]=b2[k2][1]+x2; b2[k2][2]=b2[k2][2]+1
    local k1=math.floor(l1/16); b1[k1]=b1[k1] or {0,0}; b1[k1][1]=b1[k1][1]+x1; b1[k1][2]=b1[k1][2]+1
  end
  if f>=6000 then
    local o=io.open(os.getenv("O"),"w")
    for _,pair in ipairs({{"P1",b1},{"P2",b2}}) do
      local ks={} for k in pairs(pair[2]) do ks[#ks+1]=k end table.sort(ks)
      for _,k in ipairs(ks) do local v=pair[2][k]; if v[2]>=20 then
        o:write(string.format("%s lateral %4d..%4d  mean road x %6.1f  (%d frames)",pair[1],k*16,k*16+15,v[1]/v[2],v[2])..string.char(10)) end end
    end
    o:close(); M:exit()
  end
end)
