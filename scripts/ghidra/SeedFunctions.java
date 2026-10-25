// Seed metadata recovered by dtk; no game bytes are included in this script.
// @category WarioRecomp
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;

public class SeedFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("Expected function-seed TSV");
        int created = 0, failed = 0;
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            monitor.checkCancelled();
            String[] fields = line.split("\t", 2);
            if (fields.length != 2) continue;
            Address address = toAddr(fields[0]);
            if (getFunctionAt(address) != null) continue;
            try {
                disassemble(address);
                String name = fields[1].replaceAll("[^A-Za-z0-9_]", "_");
                if (createFunction(address, name) != null) created++;
            } catch (Exception e) {
                failed++;
                if (failed <= 10) println("Seed failed " + fields[0] + ": " + e.getMessage());
            }
        }
        Address start = toAddr("80003100"), end = toAddr("801B3DDF");
        for (String[] seed : new String[][]{{"r13", "802056E0"}, {"r2", "80206100"}}) {
            Register register = currentProgram.getRegister(seed[0]);
            if (register != null)
                currentProgram.getProgramContext().setValue(register, start, end, new BigInteger(seed[1], 16));
        }
        println("dtk seed functions created=" + created + " failures=" + failed);
        println("r2/r13 assumptions are analysis context only; game bytes are unchanged.");
    }
}
