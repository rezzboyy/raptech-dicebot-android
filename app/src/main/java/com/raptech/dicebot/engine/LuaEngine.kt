package com.raptech.dicebot.engine

import com.raptech.dicebot.model.BetRecord
import com.raptech.dicebot.model.SyntaxValidationResult
import org.luaj.vm2.Globals
import org.luaj.vm2.LuaError
import org.luaj.vm2.LuaTable
import org.luaj.vm2.LuaValue
import org.luaj.vm2.Varargs
import org.luaj.vm2.lib.OneArgFunction
import org.luaj.vm2.lib.TwoArgFunction
import org.luaj.vm2.lib.VarArgFunction
import org.luaj.vm2.lib.ZeroArgFunction
import org.luaj.vm2.lib.jse.JsePlatform
import java.util.regex.Pattern

/**
 * Raptech Lua Engine (100% Compatible with Raptech Dicebot Extension & Fengari Environment).
 * Supports standard betting variables, aliases (camelCase / PascalCase), streak tracking,
 * lastBet / lastbet table, and the full suite of built-in functions.
 */
class LuaEngine(
    private val onLog: (String) -> Unit = {},
    private val onStopRequested: () -> Unit = {},
    private val onStartRequested: () -> Unit = {},
    private val onResumeRequested: () -> Unit = {},
    private val onStopOnWinRequested: () -> Unit = {},
    private val onCheckBalanceRequested: () -> Unit = {},
    private val onResetRequested: () -> Unit = {},
    private val onResetStatsRequested: () -> Unit = onResetRequested,
    private val onResetAllRequested: () -> Unit = onResetRequested,
    private val onResetSeedRequested: () -> Unit = {},
    private val onResetChartRequested: () -> Unit = {},
    private val onResetHistoryRequested: () -> Unit = {},
    private val onResetLogRequested: () -> Unit = {},
    private val onSoundRequested: () -> Unit = {}
) {

    private var globals: Globals = JsePlatform.standardGlobals()
    private var isInitialized = false
    private var currentStreak: Int = 0
    private var customScriptDelayMs: Long = 0L
    private var requestedSleepMs: Long = 0L
    private var currentSpeedBps: Double = 0.0

    companion object {
        private val LUA_ERROR_PATTERN = Pattern.compile(".*:(\\d+):\\s*(.*)")

        fun validateSyntax(script: String): SyntaxValidationResult {
            if (script.isBlank()) {
                return SyntaxValidationResult(isValid = false, errorMessage = "Skrip tidak boleh kosong.")
            }
            return try {
                val tempGlobals = JsePlatform.standardGlobals()
                tempGlobals.load(script)
                SyntaxValidationResult(isValid = true)
            } catch (e: LuaError) {
                val message = e.message ?: "Unknown syntax error"
                val matcher = LUA_ERROR_PATTERN.matcher(message)
                if (matcher.find()) {
                    val line = matcher.group(1)?.toIntOrNull()
                    val cleanMsg = matcher.group(2) ?: message
                    SyntaxValidationResult(isValid = false, errorMessage = cleanMsg, errorLine = line)
                } else {
                    SyntaxValidationResult(isValid = false, errorMessage = message)
                }
            } catch (t: Throwable) {
                SyntaxValidationResult(isValid = false, errorMessage = t.message ?: "Error kompilasi")
            }
        }

        fun autoFix(script: String): AutoFixResult = LuaScriptAutoFixer.fix(script)
    }

    fun initScript(
        script: String,
        initialBalance: Double,
        currency: String = "TRX",
        casino: String = "tronpick",
        minBet: Double = 0.0001
    ): Result<Unit> {
        return runCatching {
            globals = JsePlatform.standardGlobals()
            customScriptDelayMs = 0L
            requestedSleepMs = 0L
            currentStreak = 0

            // 1. Install Standard Library Shims (Table, Math, String, Unpack)
            installLibraryShims()

            // 2. Install Built-in Control Functions
            installBuiltinFunctions()

            // 3. Sync initial global variables and tables
            val initialBase = (initialBalance / 10000.0).coerceAtLeast(minBet)
            globals.set("base", LuaValue.valueOf(initialBase))
            globals.set("Base", LuaValue.valueOf(initialBase))
            globals.set("basebet", LuaValue.valueOf(initialBase))
            globals.set("BaseBet", LuaValue.valueOf(initialBase))
            globals.set("nextbet", LuaValue.valueOf(initialBase))
            globals.set("NextBet", LuaValue.valueOf(initialBase))
            globals.set("previousbet", LuaValue.valueOf(initialBase))
            globals.set("PreviousBet", LuaValue.valueOf(initialBase))
            globals.set("chance", LuaValue.valueOf(49.5))
            globals.set("Chance", LuaValue.valueOf(49.5))
            globals.set("bethigh", LuaValue.FALSE)
            globals.set("Bethigh", LuaValue.FALSE)
            globals.set("high", LuaValue.FALSE)
            globals.set("High", LuaValue.FALSE)
            globals.set("stopnow", LuaValue.FALSE)
            globals.set("StopNow", LuaValue.FALSE)

            syncVariables(
                currentBalance = initialBalance,
                initialBalance = initialBalance,
                minBalance = initialBalance,
                maxBalance = initialBalance,
                totalProfit = 0.0,
                currentProfit = 0.0,
                totalBets = 0L,
                totalWins = 0L,
                totalLosses = 0L,
                totalVolume = 0.0,
                currency = currency,
                casino = casino,
                minBet = minBet,
                maxBet = initialBalance,
                peakAmount = initialBase,
                largestDrawdown = 0.0,
                elapsedSeconds = 0L,
                speedBps = 0.0,
                lastRecord = null
            )

            // 4. Compile & Load user script chunk
            val chunk = globals.load(script)
            chunk.call()

            // 5. Pastikan previousbet awal sinkron dengan nilai awal taruhan yang ditentukan di skrip
            val scriptInitialBet = when {
                globals.get("nextbet").isnumber() -> globals.get("nextbet").todouble()
                globals.get("NextBet").isnumber() -> globals.get("NextBet").todouble()
                globals.get("basebet").isnumber() -> globals.get("basebet").todouble()
                globals.get("BaseBet").isnumber() -> globals.get("BaseBet").todouble()
                globals.get("base").isnumber() -> globals.get("base").todouble()
                globals.get("Base").isnumber() -> globals.get("Base").todouble()
                else -> initialBase
            }
            globals.set("previousbet", LuaValue.valueOf(scriptInitialBet))
            globals.set("PreviousBet", LuaValue.valueOf(scriptInitialBet))

            isInitialized = true
        }
    }

    private fun installLibraryShims() {
        // Run standard Lua compatibility script for table.getn, table.maxn, unpack, math.mod, math.pow, etc.
        val shimScript = """
            table.getn = function (t)
                local count = 0
                for _, __ in pairs(t) do
                    count = count + 1
                end
                return count
            end

            if table and not table.maxn then
                table.maxn = function(t)
                    local max = 0
                    for k, _ in pairs(t) do
                        if type(k) == "number" and k > max then max = k end
                    end
                    return max
                end
            end

            if not unpack and table and table.unpack then
                unpack = table.unpack
            end

            if string and not string.gfind and string.gmatch then
                string.gfind = string.gmatch
            end

            if math and not math.mod and math.fmod then
                math.mod = math.fmod
            end

            if math and not math.pow then
                math.pow = function(x, y) return x ^ y end
            end
        """.trimIndent()
        globals.load(shimScript).call()
    }

    private fun installBuiltinFunctions() {
        // print(...) & log(...)
        val printFunc = object : VarArgFunction() {
            override fun invoke(args: Varargs): Varargs {
                val sb = StringBuilder()
                for (i in 1..args.narg()) {
                    sb.append(args.arg(i).tojstring())
                    if (i < args.narg()) sb.append("\t")
                }
                onLog(sb.toString())
                return LuaValue.NONE
            }
        }
        globals.set("print", printFunc)
        globals.set("log", printFunc)

        // start() & play()
        val startFunc = object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("▶ start() dipanggil dari dalam skrip LUA.")
                onStartRequested()
                return LuaValue.NONE
            }
        }
        globals.set("start", startFunc)
        globals.set("play", startFunc)

        // stop() & pause()
        val stopFunc = object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🛑 stop() dipanggil dari dalam skrip LUA.")
                onStopRequested()
                return LuaValue.NONE
            }
        }
        globals.set("stop", stopFunc)
        globals.set("pause", stopFunc)

        // resume()
        globals.set("resume", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("⏯ resume() dipanggil dari dalam skrip LUA.")
                onResumeRequested()
                return LuaValue.NONE
            }
        })

        // stopOnWin()
        globals.set("stopOnWin", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🎯 stopOnWin() dipanggil dari dalam skrip LUA.")
                onStopOnWinRequested()
                return LuaValue.NONE
            }
        })

        // checkbalance()
        globals.set("checkbalance", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onCheckBalanceRequested()
                return LuaValue.NONE
            }
        })

        // setbalance(amount)
        globals.set("setbalance", object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue {
                val amt = arg.todouble()
                globals.set("balance", LuaValue.valueOf(amt))
                globals.set("Balance", LuaValue.valueOf(amt))
                return LuaValue.NONE
            }
        })

        // reset() & resetstats()
        val resetStatsFunc = object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🔄 resetstats() dipanggil dari dalam skrip LUA.")
                currentStreak = 0
                globals.set("currentstreak", LuaValue.valueOf(0))
                globals.set("CurrentStreak", LuaValue.valueOf(0))
                globals.set("streak", LuaValue.valueOf(0))
                globals.set("Streak", LuaValue.valueOf(0))
                globals.set("winstreak", LuaValue.valueOf(0))
                globals.set("WinStreak", LuaValue.valueOf(0))
                globals.set("losestreak", LuaValue.valueOf(0))
                globals.set("LoseStreak", LuaValue.valueOf(0))
                onResetStatsRequested()
                return LuaValue.NONE
            }
        }
        globals.set("reset", resetStatsFunc)
        globals.set("resetstats", resetStatsFunc)

        // resetall()
        globals.set("resetall", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("⚡ resetall() dipanggil dari dalam skrip LUA.")
                currentStreak = 0
                globals.set("currentstreak", LuaValue.valueOf(0))
                globals.set("CurrentStreak", LuaValue.valueOf(0))
                globals.set("streak", LuaValue.valueOf(0))
                globals.set("Streak", LuaValue.valueOf(0))
                onResetAllRequested()
                return LuaValue.NONE
            }
        })

        // resetseed()
        globals.set("resetseed", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🌱 resetseed() dipanggil dari dalam skrip LUA.")
                onResetSeedRequested()
                return LuaValue.NONE
            }
        })

        // resetchart()
        globals.set("resetchart", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("📈 resetchart() dipanggil dari dalam skrip LUA.")
                onResetChartRequested()
                return LuaValue.NONE
            }
        })

        // resethistory()
        globals.set("resethistory", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("📋 resethistory() dipanggil dari dalam skrip LUA.")
                onResetHistoryRequested()
                return LuaValue.NONE
            }
        })

        // resetlog()
        globals.set("resetlog", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🧹 resetlog() dipanggil dari dalam skrip LUA.")
                onResetLogRequested()
                return LuaValue.NONE
            }
        })

        // resetpartialprofit()
        globals.set("resetpartialprofit", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                globals.set("partialprofit", LuaValue.valueOf(0.0))
                globals.set("PartialProfit", LuaValue.valueOf(0.0))
                return LuaValue.NONE
            }
        })

        // ching() / alarm() / sound()
        val soundFunc = object : ZeroArgFunction() {
            override fun call(): LuaValue {
                onLog("🔔 [ALARM/CHIME]")
                onSoundRequested()
                return LuaValue.NONE
            }
        }
        globals.set("ching", soundFunc)
        globals.set("alarm", soundFunc)
        globals.set("sound", soundFunc)

        // sleep(seconds)
        globals.set("sleep", object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue {
                val sec = arg.todouble()
                if (sec > 0) {
                    requestedSleepMs = (sec * 1000.0).toLong()
                }
                return LuaValue.NONE
            }
        })

        // setspeed(bps), getspeed(), resetspeed()
        globals.set("setspeed", object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue {
                val bps = arg.todouble()
                customScriptDelayMs = if (bps > 0) (1000.0 / bps).toLong() else 0L
                return LuaValue.NONE
            }
        })
        globals.set("getspeed", object : ZeroArgFunction() {
            override fun call(): LuaValue = LuaValue.valueOf(currentSpeedBps)
        })
        globals.set("resetspeed", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                customScriptDelayMs = 0L
                return LuaValue.NONE
            }
        })

        // setdelay(ms), setinterval(ms), getdelay(), resetdelay()
        val setDelayFunc = object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue {
                val ms = arg.tolong()
                customScriptDelayMs = if (ms > 0) ms else 0L
                return LuaValue.NONE
            }
        }
        globals.set("setdelay", setDelayFunc)
        globals.set("setinterval", setDelayFunc)
        globals.set("getdelay", object : ZeroArgFunction() {
            override fun call(): LuaValue = LuaValue.valueOf(customScriptDelayMs.toDouble())
        })
        globals.set("resetdelay", object : ZeroArgFunction() {
            override fun call(): LuaValue {
                customScriptDelayMs = 0L
                return LuaValue.NONE
            }
        })

        // Compatibility shims: vault, unvault, invest, tip, withdraw
        globals.set("vault", object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue {
                onLog("🔒 Vault request: ${arg.todouble()}")
                return LuaValue.NONE
            }
        })
        globals.set("unvault", object : TwoArgFunction() {
            override fun call(arg1: LuaValue, arg2: LuaValue): LuaValue {
                onLog("🔓 Unvault request: ${arg1.todouble()}")
                return LuaValue.NONE
            }
        })
        globals.set("invest", object : OneArgFunction() {
            override fun call(arg: LuaValue): LuaValue = arg
        })
        globals.set("tip", object : TwoArgFunction() {
            override fun call(arg1: LuaValue, arg2: LuaValue): LuaValue {
                onLog("💡 Tip request: ${arg1.tojstring()} ${arg2.tojstring()}")
                return LuaValue.NONE
            }
        })
        globals.set("withdraw", object : TwoArgFunction() {
            override fun call(arg1: LuaValue, arg2: LuaValue): LuaValue {
                onLog("💸 Withdraw request: ${arg1.tojstring()} ${arg2.tojstring()}")
                return LuaValue.NONE
            }
        })
    }

    private fun syncVariables(
        currentBalance: Double,
        initialBalance: Double,
        minBalance: Double,
        maxBalance: Double,
        totalProfit: Double,
        currentProfit: Double,
        totalBets: Long,
        totalWins: Long,
        totalLosses: Long,
        totalVolume: Double,
        currency: String,
        casino: String,
        minBet: Double,
        maxBet: Double,
        peakAmount: Double,
        largestDrawdown: Double,
        elapsedSeconds: Long,
        speedBps: Double,
        maxWinStreak: Int = 0,
        maxLoseStreak: Int = 0,
        lastRecord: BetRecord? = null
    ) {
        currentSpeedBps = speedBps

        // 1. Balance & Sesi
        val balVal = LuaValue.valueOf(currentBalance)
        globals.set("balance", balVal)
        globals.set("Balance", balVal)

        val startBalVal = LuaValue.valueOf(initialBalance)
        globals.set("startBalance", startBalVal)
        globals.set("startbalance", startBalVal)
        globals.set("startingbalance", startBalVal)
        globals.set("StartingBalance", startBalVal)
        globals.set("initialbalance", startBalVal)

        val minBalVal = LuaValue.valueOf(minBalance)
        globals.set("minbalance", minBalVal)
        globals.set("MinBalance", minBalVal)

        val maxBalVal = LuaValue.valueOf(maxBalance)
        globals.set("maxbalance", maxBalVal)
        globals.set("MaxBalance", maxBalVal)

        // 2. Profit & Finansial
        val profVal = LuaValue.valueOf(totalProfit)
        globals.set("profit", profVal)
        globals.set("Profit", profVal)
        globals.set("totalprofit", profVal)
        globals.set("TotalProfit", profVal)

        val curProfVal = LuaValue.valueOf(currentProfit)
        globals.set("currentprofit", curProfVal)
        globals.set("CurrentProfit", curProfVal)

        if (globals.get("partialprofit").isnil()) {
            globals.set("partialprofit", LuaValue.valueOf(0.0))
            globals.set("PartialProfit", LuaValue.valueOf(0.0))
        }

        val minProfVal = LuaValue.valueOf(largestDrawdown)
        globals.set("minprofit", minProfVal)
        globals.set("MinProfit", minProfVal)

        val maxProfVal = LuaValue.valueOf(maxOf(0.0, totalProfit))
        globals.set("maxprofit", maxProfVal)
        globals.set("MaxProfit", maxProfVal)

        val pctProf = if (initialBalance > 0) (totalProfit / initialBalance) * 100.0 else 0.0
        globals.set("percentProfit", LuaValue.valueOf(pctProf))
        globals.set("percentprofit", LuaValue.valueOf(pctProf))

        val pctWagered = if (initialBalance > 0) (totalVolume / initialBalance) else 0.0
        globals.set("percentWagered", LuaValue.valueOf(pctWagered))
        globals.set("percentwagered", LuaValue.valueOf(pctWagered))

        val wagVal = LuaValue.valueOf(totalVolume)
        globals.set("wagered", wagVal)
        globals.set("Wagered", wagVal)
        globals.set("invested", wagVal)
        globals.set("totalwagered", wagVal)
        globals.set("TotalWagered", wagVal)

        // 3. Batas & Taruhan
        val minB = LuaValue.valueOf(minBet)
        globals.set("minbet", minB)
        globals.set("MinBet", minB)

        val maxB = LuaValue.valueOf(if (maxBet > 0) maxBet else currentBalance)
        globals.set("maxbet", maxB)
        globals.set("MaxBet", maxB)

        val highB = LuaValue.valueOf(peakAmount)
        globals.set("highestbet", highB)
        globals.set("HighestBet", highB)
        globals.set("maxBetAmount", highB)
        globals.set("maxbetamount", highB)

        val maxLoseAmt = LuaValue.valueOf(Math.abs(largestDrawdown))
        globals.set("maxloseamount", maxLoseAmt)
        globals.set("MaxLoseAmount", maxLoseAmt)
        globals.set("maxLosseAmount", maxLoseAmt)

        // 4. Streak & Ronde
        val isWin = lastRecord?.isWin ?: true
        val winVal = LuaValue.valueOf(isWin)
        globals.set("win", winVal)
        globals.set("Win", winVal)

        val betsVal = LuaValue.valueOf(totalBets.toDouble())
        globals.set("bets", betsVal)
        globals.set("Bets", betsVal)
        globals.set("totalbets", betsVal)
        globals.set("TotalBets", betsVal)

        val winsVal = LuaValue.valueOf(totalWins.toDouble())
        globals.set("wins", winsVal)
        globals.set("Wins", winsVal)
        globals.set("totalwins", winsVal)
        globals.set("TotalWins", winsVal)

        val lossesVal = LuaValue.valueOf(totalLosses.toDouble())
        globals.set("losses", lossesVal)
        globals.set("Losses", lossesVal)
        globals.set("totallosses", lossesVal)
        globals.set("TotalLosses", lossesVal)

        val streakVal = LuaValue.valueOf(currentStreak)
        globals.set("currentstreak", streakVal)
        globals.set("CurrentStreak", streakVal)
        globals.set("streak", streakVal)
        globals.set("Streak", streakVal)

        val wsVal = LuaValue.valueOf(if (currentStreak > 0) currentStreak else 0)
        globals.set("winstreak", wsVal)
        globals.set("WinStreak", wsVal)

        val lsVal = LuaValue.valueOf(if (currentStreak < 0) Math.abs(currentStreak) else 0)
        globals.set("losestreak", lsVal)
        globals.set("LoseStreak", lsVal)

        globals.set("maxwinstreak", LuaValue.valueOf(maxWinStreak))
        globals.set("MaxWinStreak", LuaValue.valueOf(maxWinStreak))
        globals.set("maxlosestreak", LuaValue.valueOf(maxLoseStreak))
        globals.set("MaxLoseStreak", LuaValue.valueOf(maxLoseStreak))

        // 5. Kasino & Lingkungan
        val currStr = LuaValue.valueOf(currency.lowercase())
        globals.set("currency", currStr)
        globals.set("Currency", currStr)

        val coinStr = LuaValue.valueOf(currency.uppercase())
        globals.set("coin", coinStr)
        globals.set("Coin", coinStr)

        val casStr = LuaValue.valueOf(casino.lowercase())
        globals.set("casino", casStr)
        globals.set("Casino", casStr)

        val gameStr = LuaValue.valueOf("dice")
        globals.set("game", gameStr)
        globals.set("Game", gameStr)

        val edgeVal = LuaValue.valueOf(1.0)
        globals.set("houseEdge", edgeVal)
        globals.set("houseedge", edgeVal)
        globals.set("HouseEdge", edgeVal)
        globals.set("edge", edgeVal)
        globals.set("Edge", edgeVal)

        // 6. Waktu & Kecepatan
        globals.set("time", LuaValue.valueOf(elapsedSeconds.toDouble()))
        globals.set("elapsedTime", LuaValue.valueOf(elapsedSeconds.toDouble()))
        globals.set("elapsedtime", LuaValue.valueOf(elapsedSeconds.toDouble()))
        globals.set("speed", LuaValue.valueOf(speedBps))
        globals.set("betsPerSec", LuaValue.valueOf(speedBps))
        globals.set("interval_ms", LuaValue.valueOf(customScriptDelayMs.toDouble()))
        globals.set("betdelay", LuaValue.valueOf(customScriptDelayMs.toDouble()))
        globals.set("delay", LuaValue.valueOf(customScriptDelayMs.toDouble()))

        // 7. Angka Roll Terakhir
        val rollVal = LuaValue.valueOf(lastRecord?.rollResult ?: 0.0)
        globals.set("result", rollVal)
        globals.set("Result", rollVal)
        globals.set("roll", rollVal)
        globals.set("Roll", rollVal)
        globals.set("currentroll", rollVal)
        globals.set("CurrentRoll", rollVal)
        globals.set("lastroll", rollVal)
        globals.set("LastRoll", rollVal)

        val targetVal = LuaValue.valueOf(lastRecord?.targetChance ?: 49.5)
        globals.set("target", targetVal)
        globals.set("Target", targetVal)

        // 8. lastBet & lastbet Table
        val lastBetTable = LuaTable()
        val amt = LuaValue.valueOf(lastRecord?.amount ?: minBet)
        lastBetTable.set("amount", amt)
        lastBetTable.set("Amount", amt)
        lastBetTable.set("bet", amt)
        lastBetTable.set("Bet", amt)

        val ch = LuaValue.valueOf(lastRecord?.targetChance ?: 49.5)
        lastBetTable.set("chance", ch)
        lastBetTable.set("Chance", ch)

        val r = LuaValue.valueOf(lastRecord?.rollResult ?: 0.0)
        lastBetTable.set("roll", r)
        lastBetTable.set("Roll", r)
        lastBetTable.set("result", r)
        lastBetTable.set("Result", r)

        val p = LuaValue.valueOf(lastRecord?.netResult ?: 0.0)
        lastBetTable.set("profit", p)
        lastBetTable.set("Profit", p)

        lastBetTable.set("target", ch)
        lastBetTable.set("Target", ch)

        val nonceVal = LuaValue.valueOf(lastRecord?.nonce?.toDouble() ?: 0.0)
        lastBetTable.set("nonce", nonceVal)
        lastBetTable.set("Nonce", nonceVal)
        lastBetTable.set("id", nonceVal)
        lastBetTable.set("Id", nonceVal)

        val isHigh = lastRecord?.isHigh ?: false
        val highVal = LuaValue.valueOf(isHigh)
        lastBetTable.set("bethigh", highVal)
        lastBetTable.set("Bethigh", highVal)
        lastBetTable.set("high", highVal)
        lastBetTable.set("High", highVal)

        val wVal = LuaValue.valueOf(lastRecord?.isWin ?: true)
        lastBetTable.set("win", wVal)
        lastBetTable.set("Win", wVal)

        lastBetTable.set("currency", currStr)
        lastBetTable.set("Currency", currStr)

        val payout = if ((lastRecord?.targetChance ?: 49.5) > 0) 99.0 / (lastRecord?.targetChance ?: 49.5) else 2.0
        val payoutVal = LuaValue.valueOf(payout)
        lastBetTable.set("payout", payoutVal)
        lastBetTable.set("Payout", payoutVal)
        lastBetTable.set("multiplier", payoutVal)
        lastBetTable.set("Multiplier", payoutVal)

        val condStr = LuaValue.valueOf(if (isHigh) "above" else "below")
        lastBetTable.set("condition", condStr)
        lastBetTable.set("Condition", condStr)
        lastBetTable.set("serverSeed", LuaValue.valueOf(""))
        lastBetTable.set("clientSeed", LuaValue.valueOf(""))

        globals.set("lastBet", lastBetTable)
        globals.set("lastbet", lastBetTable)
    }

    fun getInitialBetDecision(): NextBetDecision {
        if (!isInitialized) {
            return NextBetDecision(amount = 0.00000001, chance = 49.5, isHigh = false)
        }

        // Check nextbet / NextBet first
        var amount = 0.0
        val nb = globals.get("nextbet")
        val nbUpper = globals.get("NextBet")
        if (nb.isnumber()) {
            amount = nb.todouble()
        } else if (nbUpper.isnumber()) {
            amount = nbUpper.todouble()
        }

        // Fallback to basebet / base / BaseBet / Base
        if (amount <= 0.0) {
            val bb = globals.get("basebet")
            val b = globals.get("base")
            val bbUpper = globals.get("BaseBet")
            val bUpper = globals.get("Base")
            amount = when {
                bb.isnumber() -> bb.todouble()
                b.isnumber() -> b.todouble()
                bbUpper.isnumber() -> bbUpper.todouble()
                bUpper.isnumber() -> bUpper.todouble()
                else -> 0.00000001
            }
        }

        val chanceVal = if (globals.get("chance").isnumber()) globals.get("chance") else globals.get("Chance")
        val chance = if (chanceVal.isnumber()) chanceVal.todouble().coerceIn(0.01, 98.0) else 49.5

        val betHighVal = when {
            globals.get("bethigh").isboolean() -> globals.get("bethigh")
            globals.get("Bethigh").isboolean() -> globals.get("Bethigh")
            globals.get("high").isboolean() -> globals.get("high")
            globals.get("High").isboolean() -> globals.get("High")
            else -> LuaValue.FALSE
        }
        val isHigh = betHighVal.toboolean()

        return NextBetDecision(
            amount = amount.coerceAtLeast(0.00000001),
            chance = chance,
            isHigh = isHigh
        )
    }

    fun onRollCompleted(
        lastRecord: BetRecord,
        currentBalance: Double,
        totalProfit: Double,
        totalBets: Long,
        totalWins: Long,
        totalLosses: Long,
        totalVolume: Double,
        currency: String = "TRX",
        initialBalance: Double = currentBalance,
        minBalance: Double = currentBalance,
        maxBalance: Double = currentBalance,
        currentProfit: Double = lastRecord.netResult,
        winStreak: Int = if (lastRecord.isWin) 1 else 0,
        loseStreak: Int = if (!lastRecord.isWin) 1 else 0,
        maxWinStreak: Int = winStreak,
        maxLoseStreak: Int = loseStreak,
        peakAmount: Double = lastRecord.amount,
        largestDrawdown: Double = totalProfit,
        casino: String = "tronpick",
        minBet: Double = 0.0001,
        elapsedSeconds: Long = 0L,
        speedBps: Double = 0.0
    ): NextBetDecision {
        if (!isInitialized) {
            return NextBetDecision(amount = currentBalance / 10000.0, chance = 49.5, isHigh = false)
        }

        try {
            // Update streak tracking
            currentStreak = if (lastRecord.isWin) {
                if (currentStreak > 0) currentStreak + 1 else 1
            } else {
                if (currentStreak < 0) currentStreak - 1 else -1
            }

            // Sync all runtime variables
            syncVariables(
                currentBalance = currentBalance,
                initialBalance = initialBalance,
                minBalance = minBalance,
                maxBalance = maxBalance,
                totalProfit = totalProfit,
                currentProfit = currentProfit,
                totalBets = totalBets,
                totalWins = totalWins,
                totalLosses = totalLosses,
                totalVolume = totalVolume,
                currency = currency,
                casino = casino,
                minBet = minBet,
                maxBet = currentBalance,
                peakAmount = peakAmount,
                largestDrawdown = largestDrawdown,
                elapsedSeconds = elapsedSeconds,
                speedBps = speedBps,
                maxWinStreak = maxWinStreak,
                maxLoseStreak = maxLoseStreak,
                lastRecord = lastRecord
            )

            // Update previousbet to last bet amount
            val prevBetVal = LuaValue.valueOf(lastRecord.amount)
            globals.set("previousbet", prevBetVal)
            globals.set("PreviousBet", prevBetVal)

            // Execute dobet() hook
            val dobetFunc = globals.get("dobet")
            if (dobetFunc.isfunction()) {
                dobetFunc.call()
            }

            // Check if stopnow / StopNow was set to true
            val stopNow = globals.get("stopnow").optboolean(false) || globals.get("StopNow").optboolean(false)
            if (stopNow) {
                onLog("🛑 stopnow terdeteksi bernilai true dari dalam skrip LUA.")
                onStopRequested()
            }

            // Read next bet decision with all fallback aliases
            var amount = 0.0
            val nb = globals.get("nextbet")
            val nbUpper = globals.get("NextBet")
            if (nb.isnumber()) {
                amount = nb.todouble()
            } else if (nbUpper.isnumber()) {
                amount = nbUpper.todouble()
            }

            if (amount <= 0.0) {
                val bb = globals.get("basebet")
                val b = globals.get("base")
                val bbUpper = globals.get("BaseBet")
                val bUpper = globals.get("Base")
                amount = when {
                    bb.isnumber() -> bb.todouble()
                    b.isnumber() -> b.todouble()
                    bbUpper.isnumber() -> bbUpper.todouble()
                    bUpper.isnumber() -> bUpper.todouble()
                    else -> lastRecord.amount
                }
            }

            val chanceVal = if (globals.get("chance").isnumber()) globals.get("chance") else globals.get("Chance")
            val chance = if (chanceVal.isnumber()) chanceVal.todouble().coerceIn(0.01, 98.0) else 49.5

            val betHighVal = when {
                globals.get("bethigh").isboolean() -> globals.get("bethigh")
                globals.get("Bethigh").isboolean() -> globals.get("Bethigh")
                globals.get("high").isboolean() -> globals.get("high")
                globals.get("High").isboolean() -> globals.get("High")
                else -> LuaValue.valueOf(lastRecord.isHigh)
            }
            val isHigh = betHighVal.toboolean()

            // Check custom script delays
            val luaDelay = when {
                globals.get("interval_ms").isnumber() && globals.get("interval_ms").todouble() >= 0 -> globals.get("interval_ms").tolong()
                globals.get("betdelay").isnumber() && globals.get("betdelay").todouble() >= 0 -> globals.get("betdelay").tolong()
                globals.get("delay").isnumber() && globals.get("delay").todouble() >= 0 -> globals.get("delay").tolong()
                else -> null
            }
            if (luaDelay != null) {
                customScriptDelayMs = luaDelay
            }

            return NextBetDecision(
                amount = amount.coerceAtLeast(0.00000001),
                chance = chance,
                isHigh = isHigh
            )
        } catch (e: LuaError) {
            onLog("❌ Runtime LUA Error: ${e.message}")
            return NextBetDecision(amount = lastRecord.amount, chance = lastRecord.targetChance, isHigh = lastRecord.isHigh)
        }
    }

    fun consumeSleepDelayMs(): Long {
        val delay = requestedSleepMs
        requestedSleepMs = 0L
        return delay
    }

    fun getCustomScriptDelayMs(): Long = customScriptDelayMs

    data class NextBetDecision(
        val amount: Double,
        val chance: Double,
        val isHigh: Boolean
    )
}
