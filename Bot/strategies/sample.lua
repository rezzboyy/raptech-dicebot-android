--JP CILIK

function incr(x,y)
    return x + (x * (y/100))
end

function decr(x,y)
    return x - (x * (y/100))
end

target  = balance * 50000
basebet = 5e-7---balance*9e-8
betlose = 0
sumlose = 0
nextbet = basebet
chance  = 15
profitc = 0
sesi    = basebet
stopwin = false

function dobet()
    if win then
        info = " [ "..bethold(balance, basebet, 1.256, 1).." ]"
    end
    profitc = profitc + currentprofit
    if profitc >= sesi then
        if stopwin then stop() end
        profitc = 0
        chance  = math.random(451,1910)/100
        nextbet = basebet
        betlose = 0
        resetpartialprofit()
    else
        if win then
            betlose = 0
            nextbet = basebet
        else
            sumlose = sumlose + 1
            betlose = betlose + 1
            chance  = decr(chance, 1.5)
            nextbet = incr(nextbet, 25.6)
            if (sumlose%25 == 0) then chance = incr(chance, 15) end
            if (betlose == 35) then chance = incr(chance, 50) end
            if (betlose == 45) then chance = incr(chance, 45) end
            if (betlose == 55) then chance = incr(chance, 55) end
        end
    end
    if betlose > 35 then 
        info = " onstreak" 
        
    end
    if balance > target then stop() end
    manageRisk()
    -- if cdrop/mbal*100 > 8 then 
    --      nextbet = peakb/((99/chance)-1)*-1.01
    -- end
end

ifpause  = 0
ifdrop   = 30
ifprofit = 500

info = ""
sbal,mbal = balance,balance
cdrop,mdrop = 0,0
stwin = false
pswin = false
stbal = balance+(balance*(ifprofit/100))
peakb = 0
function manageRisk()

    peakb = peakb + currentprofit
    if peakb > 0 then
        peakb = 0
        if stwin then stop() end
        if pswin then pause() pswin = false end
        if currentprofit/sbal*100 > ifpause and ifpause > 0 then pause() end
    end

    mbal  = math.max(mbal,balance)
    cdrop = peakb*-1
    mdrop = math.max(mdrop,cdrop)

    if cdrop/mbal*100 > ifdrop and ifdrop > 0 then pswin = true end
    if balance > stbal and stbal > 0 then stop() end

    incdrop = string.format("[ %.5f ] ", cdrop)
    inmdrop = string.format("[ %.5f ]", mdrop) .. string.format(" [ %.2f ] ", mdrop/mbal*100)
    incdeep = string.format("( %.2f/%.2f ) ",profit/sbal*100,mdrop/sbal*100)
    print("++ drop " .. incdrop .. inmdrop .. incdeep .. info)
end

function bethold(balance, nextBet, multiplier, loseStep)
    if balance <= 0 or nextBet <= 0 or loseStep <= 0 then return 0 end
    if nextBet > balance then return 0 end
    if multiplier == 1 then
        return math.floor(balance / nextBet)
    end
    local biayaSiklusAwal = loseStep * nextBet
    local n_siklus = math.log((balance * (multiplier - 1) / biayaSiklusAwal) + 1) / math.log(multiplier)
    local siklus_penuh = math.floor(n_siklus)
    local total_biaya_siklus = biayaSiklusAwal * (multiplier^siklus_penuh - 1) / (multiplier - 1)
    local sisa_balance = balance - total_biaya_siklus
    local total_bet = siklus_penuh * loseStep
    local bet_berikutnya = nextBet * (multiplier^siklus_penuh)
    local sisa_bet_terakhir = math.floor(sisa_balance / bet_berikutnya)
    if sisa_bet_terakhir > loseStep then
        sisa_bet_terakhir = loseStep
    end
    return total_bet + sisa_bet_terakhir
end