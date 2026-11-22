package com.raptech.dicebot

import com.raptech.dicebot.engine.LuaEngine
import com.raptech.dicebot.engine.LuaScriptAutoFixer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LuaScriptAutoFixerTest {

    @Test
    fun testEmptyScriptGeneratesValidDefault() {
        val result = LuaScriptAutoFixer.fix("   ")
        assertTrue("Skrip kosong harus dimodifikasi", result.isModified)
        assertTrue("Hasil harus valid", result.isValid)
        assertTrue("Harus mengandung function dobet()", result.fixedScript.contains("function dobet()"))
        assertTrue("Harus mengandung basebet", result.fixedScript.contains("basebet ="))
        assertTrue("Harus mengandung chance", result.fixedScript.contains("chance ="))
    }

    @Test
    fun testFixJsOperatorsAndComments() {
        val brokenScript = """
            // Inisialisasi taruhan
            basebet = 0.0001
            nextbet = basebet
            chance = 49.5
            bethigh = true

            /* Callback utama */
            function dobet()
                if (win != true && balance > 0) then
                    nextbet = previousbet * 2
                else
                    nextbet = basebet
                end
            end
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(brokenScript)
        assertTrue("Harus memodifikasi skrip", result.isModified)
        assertTrue("Sintaks setelah difix harus valid: ${result.errorMessage}", result.isValid)
        assertFalse("Tidak boleh ada '//'", result.fixedScript.contains("//"))
        assertFalse("Tidak boleh ada '/*'", result.fixedScript.contains("/*"))
        assertFalse("Tidak boleh ada '!='", result.fixedScript.contains("!="))
        assertFalse("Tidak boleh ada '&&'", result.fixedScript.contains("&&"))
        assertTrue("Harus dikonversi ke '~='", result.fixedScript.contains("~="))
        assertTrue("Harus dikonversi ke 'and'", result.fixedScript.contains(" and "))
    }

    @Test
    fun testFixMissingThenAndMissingEnd() {
        val brokenScript = """
            basebet = 0.0001
            nextbet = basebet
            chance = 49.5
            bethigh = true

            function dobet()
                if win
                    nextbet = basebet
                else
                    nextbet = previousbet * 2
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(brokenScript)
        assertTrue("Harus memodifikasi skrip", result.isModified)
        assertTrue("Sintaks setelah difix harus valid: ${result.errorMessage}", result.isValid)
        assertTrue("Harus ada 'then'", result.fixedScript.contains("if win then"))
        // Check with LuaEngine directly
        val validation = LuaEngine.validateSyntax(result.fixedScript)
        assertTrue("LuaEngine harus memvalidasi skrip sebagai valid: ${validation.errorMessage}", validation.isValid)
    }

    @Test
    fun testFixCompoundAssignmentsAndBraces() {
        val brokenScript = """
            basebet = 0.0001;
            nextbet = basebet;
            chance = 49.5;
            bethigh = true;

            function dobet() {
                if (win == false) {
                    nextbet *= 2;
                } else {
                    nextbet = basebet;
                }
            }
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(brokenScript)
        assertTrue("Harus memodifikasi skrip", result.isModified)
        assertTrue("Sintaks setelah difix harus valid: ${result.errorMessage}", result.isValid)
        assertFalse("Tidak boleh mengandung '{'", result.fixedScript.contains("{"))
        assertFalse("Tidak boleh mengandung '}'", result.fixedScript.contains("}"))
        assertFalse("Tidak boleh mengandung '*='", result.fixedScript.contains("*="))
        val validation = LuaEngine.validateSyntax(result.fixedScript)
        assertTrue("Validasi LuaEngine harus berhasil: ${validation.errorMessage}", validation.isValid)
    }

    @Test
    fun testWrapsLogicInDobetIfMissing() {
        val bareLogic = """
            basebet = 0.0002
            chance = 49.5
            bethigh = true

            if win then
                nextbet = basebet
            else
                nextbet = previousbet * 2
            end
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(bareLogic)
        assertTrue("Harus membungkus ke function dobet()", result.fixedScript.contains("function dobet()"))
        assertTrue("Harus valid", result.isValid)
        val validation = LuaEngine.validateSyntax(result.fixedScript)
        assertTrue("Validasi LuaEngine harus berhasil", validation.isValid)
    }

    @Test
    fun testAddsMissingVariables() {
        val scriptWithoutVars = """
            function dobet()
                if win then
                    print("win")
                end
            end
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(scriptWithoutVars)
        assertTrue("Harus mendeklarasikan nextbet jika tidak ada", result.fixedScript.contains("nextbet ="))
        assertTrue("Harus valid", result.isValid)
    }

    @Test
    fun testFixStrayTokenSyntaxErrorLikeUserScreenshot() {
        val brokenScript = """
            basebet = 0.0001
            nextbet = basebet
            chance = 49.5
            bethigh = true

            function dobet()
                if win then
                    nextbet = basebet
                else
                    nextbet = previousbet * 2
                end
            end

            ub
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(brokenScript)
        assertTrue("Harus memodifikasi skrip", result.isModified)
        assertTrue("Skrip harus valid setelah AutoFix mengobati error 'ub': ${result.errorMessage}", result.isValid)
        val validation = LuaEngine.validateSyntax(result.fixedScript)
        assertTrue("Validasi LuaEngine harus berhasil: ${validation.errorMessage}", validation.isValid)
    }

    @Test
    fun testUserScript1And2And3() {
        val script1 = """
            base          = 2e-8 
            ch_index      = {5, 20, 7, 14, 18, 26, 1}  
            chance        = 90  
            nextbet       = base  
             
            trigger_streak   = -9 
            trigger_drop_pct = 1.0 
             
            ifpause       = 0 
            ifdrop        = 0 
            ifprofit      = 5000000 
             
            info          = "" 
            sbal, mbal    = balance, balance 
            cdrop, mdrop  = 0, 0 
            stwin         = false 
            pswin         = false 
            stbal         = balance + (balance * (ifprofit / 100)) 
            peakb         = 0 
             
            function dobet()  
                updateRiskMetrics() 
             
                if win then  
                    nextbet = previousbet * 0.8  
             
                    if (currentstreak == 1) then  
                        chance = math.random(7, 14)   
                    else  
                        chance = ch_index[math.random(1, #ch_index)]  
                    end  
                    info = "" 
                else  
                    local abs_streak = math.abs(currentstreak)  
             
                    local is_hybrid_triggered = (currentstreak <= trigger_streak) or ((cdrop / mbal * 100) >= trigger_drop_pct) 
             
                    if is_hybrid_triggered and partialprofit < 0 then 
                        manageRecovery() 
                    else 
                        local lossmult = 1 
                        if (abs_streak <= 5) then 
                            lossmult = chance + 10 
                        else 
                            lossmult = chance + 25 
                        end 
             
                        chance = ch_index[math.random(1, #ch_index)] 
             
                        nextbet = previousbet + (previousbet * (lossmult / 100))  
                        info = ""  
                    end 
                end  
                 
                if partialprofit >= 0 then   
                    nextbet = base  
                    chance  = 90    
                    resetpartialprofit()  
                end  
             
                manageRisk() 
            end 
             
            function manageRecovery() 
                local multi = 1 
                local is_recovery = false 
             
                chance = ch_index[math.random(1, #ch_index)] 
             
                if currentstreak <= -30 or (cdrop / mbal * 100) >= 5.0 then  
                    multi       = math.random(105, 110) / 100  
                    is_recovery = true 
                elseif currentstreak <= -15 or (cdrop / mbal * 100) >= 2.5 then  
                    multi = math.random(130, 150) / 100  
                    is_recovery = true 
                elseif currentstreak <= -9 or (cdrop / mbal * 100) >= 1.0 then  
                    multi = math.random(110, 125) / 100  
                    is_recovery = true 
                end  
                 
                if is_recovery then 
                    local payout_multiplier = (99 / math.min(chance, 98)) - 1 
                    payout_multiplier = math.max(0.05, payout_multiplier) 
             
                    local betload = math.abs(partialprofit) / payout_multiplier   
                    nextbet = betload * multi 
                    info = string.format(" [HYBRID-REC: %.2fx] ", multi) 
                else 
                    info = "" 
                end 
                 
                nextbet = math.max(nextbet, base) 
            end 
             
            function updateRiskMetrics() 
                peakb = peakb + currentprofit 
                if peakb > 0 then 
                    peakb = 0 
                    if stwin then stop() end 
                    if pswin then pause() pswin = false end 
                    if currentprofit / sbal * 100 > ifpause and ifpause > 0 then pause() end 
                end 
             
                mbal  = math.max(mbal, balance) 
                cdrop = peakb * -1 
                mdrop = math.max(mdrop, cdrop) 
            end 
             
            function manageRisk() 
                if cdrop / mbal * 100 > ifdrop and ifdrop > 0 then pswin = true end 
                if balance > stbal and stbal > 0 then stop() end 
             
                local incdrop = string.format("[ %.8f ] ", cdrop) 
                local inmdrop = string.format("[ %.8f ]", mdrop) .. string.format(" [ %.2f%% ] ", mdrop / mbal * 100) 
                local incdeep = string.format("( %.2f%% / %.2f%% ) ", profit / sbal * 100, mdrop / sbal * 100) 
                print("++ drop " .. incdrop .. inmdrop .. incdeep .. info) 
            end
        """.trimIndent()

        val fixRes1 = LuaScriptAutoFixer.fix(script1)
        assertFalse("AutoFix tidak boleh memaksa menginjeksi bethigh pada Script 1", fixRes1.fixedScript.startsWith("bethigh ="))
        assertFalse("AutoFix tidak boleh ada pesan bethigh", fixRes1.changes.any { it.contains("bethigh") })

        val engine = LuaEngine()
        val initRes = engine.initScript(script1, initialBalance = 100.0, minBet = 0.0001)
        println("Init script 1 result: " + initRes.isSuccess + " " + initRes.exceptionOrNull()?.message)
        assertTrue("Script 1 harus berhasil diinit: " + initRes.exceptionOrNull()?.message, initRes.isSuccess)

        val decision = engine.getInitialBetDecision()
        assertTrue("Script 1 nextbet harus > 0", decision.amount > 0)
        println("Script 1 initial decision: amount=${decision.amount}, chance=${decision.chance}, isHigh=${decision.isHigh}")
    }

    @Test
    fun testUserScript3InitSeed() {
        val script3 = """
            basemtp = 0.000005
            function init_dobet()
                resetclientseed()
                basebet = balance*basemtp
                chance  = 13.38
                nextbet = basebet
                basech  = chance
                count   = 1
                streak  = 0
                xstreak = 0
                rstreak = 17
                pstreak = 0
                ctdecay = 0
                bethigh = math.random(2)==1
            end
            init_dobet()

            function dobet()
                if partialprofit > 0 then
                    resetpartialprofit()
                    info    = "  [ WIN ]"
                    nextbet = basebet
                    chance  = basech
                    if xstreak > rstreak+pstreak then
                        pstreak = xstreak - (rstreak+pstreak)
                    end
                    streak  = 0
                    ctdecay = 0
                else
                    if win then
                        streak  = 0
                        chance  = chance - 0.5
                        nextbet = basebet
                        ctdecay = 0
                    end
                    if currentstreak+pstreak < 0 then
                        streak  = streak + 1
                        nextbet = previousbet * 1.38 
                        chance  = chance + 0.1
                        if streak > rstreak+pstreak then
                            chance  = chance - 0.05 
                            ctdecay = ctdecay + 1
                            decay   = 1.2-(ctdecay/100)
                            nextbet = math.abs(partialprofit)/((99/chance)-1)*decay
                        end
                        xstreak = math.max(xstreak,streak)
                    end
                    info = string.format("  [ %d / %d ] [ %d ] +%d",streak,xstreak,rstreak+pstreak,pstreak)
                end 
                nextbet = math.max(nextbet,basebet)
                manageRisk()
                if cdrop/mbal*100 > ifrecov and ifrecov > 0 then 
                   nextbet = peakb/((99/chance)-1)*-1.01
                end
            end

            ifrecov  = 0
            ifpause  = 0
            ifdrop   = 20
            ifprofit = 1000

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
        """.trimIndent()

        val fixRes3 = LuaScriptAutoFixer.fix(script3)
        assertFalse("AutoFix tidak boleh memaksa menginjeksi bethigh pada Script 3", fixRes3.fixedScript.startsWith("bethigh ="))
        assertFalse("AutoFix tidak boleh ada pesan bethigh", fixRes3.changes.any { it.contains("bethigh") })

        val engine = LuaEngine()
        val initRes = engine.initScript(script3, initialBalance = 100.0, minBet = 0.0001)
        println("Init script 3 result: " + initRes.isSuccess + " " + initRes.exceptionOrNull()?.message)
        assertTrue("Script 3 harus berhasil diinit: " + initRes.exceptionOrNull()?.message, initRes.isSuccess)

        // Execute initial bet decision
        val decision = engine.getInitialBetDecision()
        assertTrue("Jumlah taruhan harus > 0", decision.amount > 0)
        println("Script 3 initial decision: amount=${decision.amount}, chance=${decision.chance}, isHigh=${decision.isHigh}")
    }
}
