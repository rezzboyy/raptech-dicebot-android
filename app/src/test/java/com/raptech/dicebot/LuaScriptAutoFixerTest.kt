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
                    nextbet = basebet
                else
                    nextbet = previousbet * 2
                end
            end
        """.trimIndent()

        val result = LuaScriptAutoFixer.fix(scriptWithoutVars)
        assertTrue("Harus mendeklarasikan basebet", result.fixedScript.contains("basebet ="))
        assertTrue("Harus mendeklarasikan chance", result.fixedScript.contains("chance ="))
        assertTrue("Harus mendeklarasikan bethigh", result.fixedScript.contains("bethigh ="))
        assertTrue("Harus valid", result.isValid)
    }
}
