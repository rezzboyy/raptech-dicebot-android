package com.raptech.dicebot.model

data class StrategyPreset(
    val name: String,
    val description: String,
    val category: String,
    val script: String
)

object StrategyPresets {

    val RAPTECH_PICKIO_PRO = StrategyPreset(
        name = "Raptech Pick.io Pro",
        description = "Strategi resmi Raptech Automation untuk seluruh keluarga Pick.io dengan auto reset seed & dynamic recovery",
        category = "Official Raptech",
        script = """--[[
    RAPTECH AUTOMATION CONSOLE - PICK.IO PRO STRATEGY
    Tronpick, Dogepick, Litepick, Bnbpick, Solpick, Polpick, etc.
]]

base = math.max(0.0001, balance / 10000.0)
target = balance * 0.15
stopLoss = balance * 0.30

nextbet = base
chance = 49.5
bethigh = false

function dobet()
    if profit >= target then
        print(string.format("TARGET OPIT REACHED: +%.8f %s! Stopping.", profit, currency))
        stop()
    end
    if profit <= -stopLoss then
        print(string.format("STOP LOSS HIT: %.8f %s! Stopping.", profit, currency))
        stop()
    end

    if win then
        print(string.format("[WIN #%d] Roll: %.2f | Profit: +%.8f", bets, lastBet.roll, lastBet.profit))
        nextbet = base
        chance = 49.5
    else
        print(string.format("[LOSE #%d] Roll: %.2f | Streak: %d", bets, lastBet.roll, currentstreak))
        if math.abs(currentstreak) >= 3 then
            resetseed()
        end
        nextbet = previousbet * 2.0
    end
end
"""
    )

    val XCODE_SAFE_RECOVERY = StrategyPreset(
        name = "Xcode Safe Recovery",
        description = "Chance dinamis adaptif dengan formula recovery payout tinggi",
        category = "Xcode Series",
        script = """--[[
    XCODE SAFE RECOVERY STRATEGY
    Adaptive Multiplier & Smart Drawdown Recovery
]]

baseChance       = 50
chanceStep       = 0.5
maxLoseStreak    = 2
recoveryChance   = 7.10
basebet          = balance / 1000000.0
nextbet          = basebet
chance           = baseChance
inRecovery       = false
totalLost        = 0

target           = balance * 0.05
stopLoss         = balance * 0.20

function calculateRecoveryBet()
    local payout = 99.0 / chance
    if payout <= 1 then payout = 1.01 end
    local baseRecover = (totalLost + basebet * 0.5)
    return (baseRecover / (payout - 1)) * 1.15
end

function dobet()
    if profit >= target then
        print("🎯 TARGET TERCAPAI: +" .. profit)
        stop()
    elseif profit <= -stopLoss then
        print("🛑 STOP LOSS TERCAPAI: " .. profit)
        stop()
    end

    if win then
        print("✓ MENANG! Reset ke basebet.")
        totalLost = 0
        chance = baseChance
        nextbet = basebet
        inRecovery = false
    else
        totalLost = totalLost + previousbet
        if math.abs(currentstreak) >= maxLoseStreak then
            inRecovery = true
            chance = recoveryChance
            nextbet = calculateRecoveryBet()
            print(string.format("⚡ Masuk RECOVERY MODE! NextBet: %.8f, Chance: %.2f", nextbet, chance))
        else
            chance = math.max(10.0, chance - chanceStep)
            nextbet = previousbet * 1.5
            print(string.format("⚠ Lose #%d. NextBet: %.8f, Chance: %.2f", math.abs(currentstreak), nextbet, chance))
        end
    end
end
"""
    )

    val MARTINGALE_CLASSIC = StrategyPreset(
        name = "Classic Martingale",
        description = "Penggandaan standar x2 saat kalah, reset ke base saat menang",
        category = "Standard",
        script = """--[[
    CLASSIC MARTINGALE STRATEGY
]]

base = balance / 500000.0
nextbet = base
chance = 49.5
bethigh = false

targetProfit = balance * 0.10
maxStopLoss = balance * 0.30

function dobet()
    if profit >= targetProfit then
        print("Target Profit 10% Terpenuhi! Stop.")
        stop()
    end
    if profit <= -maxStopLoss then
        print("Stop Loss 30% Tersentuh! Stop.")
        stop()
    end

    if win then
        nextbet = base
        print("Win! Reset: " .. nextbet)
    else
        nextbet = previousbet * 2.0
        print(string.format("Loss Streak: %d -> Next: %.8f", currentstreak, nextbet))
    end
end
"""
    )

    val DALEMBERT_SCALPER = StrategyPreset(
        name = "D'Alembert Scalper",
        description = "Penambahan 1 unit saat kalah dan pengurangan 1 unit saat menang",
        category = "Low Risk",
        script = """--[[
    D'ALEMBERT LOW RISK STRATEGY
]]

unit = balance / 1000000.0
units = 1
nextbet = unit * units
chance = 49.5
bethigh = false

function dobet()
    if win then
        units = math.max(1, units - 1)
        nextbet = unit * units
        print("Win: Turun ke unit " .. units)
    else
        units = units + 1
        nextbet = unit * units
        print("Loss: Naik ke unit " .. units)
    end
end
"""
    )

    val ALL_PRESETS = listOf(
        RAPTECH_PICKIO_PRO,
        XCODE_SAFE_RECOVERY,
        MARTINGALE_CLASSIC,
        DALEMBERT_SCALPER
    )
}
