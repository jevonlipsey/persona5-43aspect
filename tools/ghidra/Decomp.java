// Decompile functions of P5R.exe by rva. args: <out-dir> <rva-hex>...
// The project is opened read-only, so functions created here are not persisted.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class Decomp extends GhidraScript {
    Function ensure(Address ad) {
        Function f = currentProgram.getFunctionManager().getFunctionContaining(ad);
        if (f != null) return f;
        new DisassembleCommand(ad, null, true).applyTo(currentProgram, monitor);
        new CreateFunctionCmd(ad).applyTo(currentProgram, monitor);
        return currentProgram.getFunctionManager().getFunctionAt(ad);
    }

    // append f32/f64 values to constant globals read from the image
    String annotate(String c) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\b(_?(?:UNK|DAT)_([0-9a-f]{9}))\\b").matcher(c);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
            String note = "";
            try {
                Address ad = toAddr("0x" + m.group(2));
                int bits = currentProgram.getMemory().getInt(ad);
                note = " /*f32=" + Float.intBitsToFloat(bits) + " i32=" + bits + "*/";
            } catch (Exception e) { }
            m.appendReplacement(sb, m.group(1) + note);
        }
        m.appendTail(sb);
        return sb.toString();
    }

    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        File out = new File(a[0]);
        out.mkdirs();
        Address base = currentProgram.getImageBase();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (int i = 1; i < a.length; i++) {
            Address ad = base.add(Long.parseLong(a[i], 16));
            Function fn = ensure(ad);
            if (fn == null) { println("FAIL(no function) " + a[i]); continue; }
            DecompileResults r = di.decompileFunction(fn, 120, monitor);
            String file = "sub_" + a[i] + ".c";
            if (r.decompileCompleted()) {
                try (PrintWriter pw = new PrintWriter(new File(out, file))) {
                    pw.println(annotate(r.getDecompiledFunction().getC()));
                }
                println("OK " + a[i] + " -> " + file);
            } else println("FAIL " + a[i] + ": " + r.getErrorMessage());
        }
        di.dispose();
    }
}
