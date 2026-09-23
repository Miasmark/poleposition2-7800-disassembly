-- integrity.lua -- every frame, is any of player 2's road headers zeroed?
-- (a road object's graphics page is never 0 in a healthy list)
local M=(type(manager.machine)=="function") and manager:machine() or manager.machine
local mem=M.devices[":maincpu"].spaces["program"]
local addrs={}
for h in string.gmatch(io.open(os.getenv("HDR")):read("*l"),"%x+") do addrs[#addrs+1]=tonumber(h,16) end
local f,bad,first=0,0,nil
emu.register_frame_done(function()
  f=f+1
  local st=mem:read_u8(0x9D)
  if st==2 or st==3 then
    for _,a in ipairs(addrs) do
      if mem:read_u8(a)==0 then bad=bad+1; if not first then first=f end; break end
    end
  end
  if f>=tonumber(os.getenv("FR")) then
    local o=io.open(os.getenv("O"),"w")
    o:write(string.format("racing frames with a zeroed road header: %d%s",bad,first and (" (first at f"..first..")") or "")..string.char(10))
    o:close(); M:exit()
  end
end)
