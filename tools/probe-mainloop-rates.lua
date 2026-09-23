-- rates.lua -- how often does each main-loop step run? Count opcode fetches at
-- exact PCs (a read tap on the instruction's own address, PC-checked so MARIA
-- DMA and data reads are not counted).
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local cpu=M.devices[":maincpu"]
local mem=cpu.spaces["program"]
local out=os.getenv("R_OUT") or "rates"
local a,b=1400,3600
local SITES={ {0xD259,"main loop pass (STA $BB)"}, {0xEA2C,"stage copy after wait"},
              {0xE70D,"object DL rebuild (JSR E6D7)"}, {0xE710,"then JSR E320"} }
local f=0
local cnt={}
TAPS={}
for i,s in ipairs(SITES) do
  cnt[i]=0
  TAPS[i]=mem:install_read_tap(s[1],s[1],"r"..i,function(o,d)
    if f>=a and f<=b and cpu.state["PC"].value==s[1] then cnt[i]=cnt[i]+1 end
    return d end)
end
emu.register_frame_done(function()
  f=f+1
  if f>b then
    local o=io.open(out..".txt","w")
    for i,s in ipairs(SITES) do
      o:write(string.format("%-32s %6d runs in %d frames = once every %.2f frames",
        s[2],cnt[i],b-a+1,(b-a+1)/math.max(cnt[i],1))..string.char(10))
    end
    o:close(); M:exit()
  end
end)
