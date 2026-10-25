// Save selected decompiler evidence only in the caller's private output folder.
// @category WarioRecomp
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportBootstrap extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("Expected private output directory");
        Path output = Path.of(args[0]);
        Files.createDirectories(output);
        DecompInterface decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Cannot open decompiler");
            StringBuilder summary = new StringBuilder();
            summary.append("Language: ").append(currentProgram.getLanguageID()).append('\n');
            summary.append("Functions: ").append(currentProgram.getFunctionManager().getFunctionCount()).append('\n');
            for (String address : new String[]{"8002FC00", "801A87C4", "8004AA14", "801A4158", "801A11A8"}) {
                Function function = getFunctionAt(toAddr(address));
                if (function == null) {
                    summary.append(address).append(" no function\n");
                    continue;
                }
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                if (result.decompileCompleted()) {
                    Files.writeString(output.resolve(address + ".c"), result.getDecompiledFunction().getC());
                    summary.append(address).append(' ').append(function.getName()).append(" exported\n");
                } else {
                    summary.append(address).append(" failed: ").append(result.getErrorMessage()).append('\n');
                }
            }
            Files.writeString(output.resolve("summary.txt"), summary.toString());
            println(summary.toString());
        } finally {
            decompiler.dispose();
        }
    }
}
