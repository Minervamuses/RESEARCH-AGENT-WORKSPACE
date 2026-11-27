import os from "node:os";
import { performance } from "node:perf_hooks";
import { parseOutline } from "../../../../../app/desktop/src/lib/outline/index.ts";

function buildMarkdownDoc(targetBytes: number, headingCount: number): string {
  const parts: string[] = ["---\ntitle: Benchmark Document\n---\n\n"];
  const fillerLine = "中英混合測試 with [@smith2020].\n";
  const fillerBytes = Buffer.byteLength(fillerLine, "utf8");
  for (let i = 0; i < headingCount; i += 1) {
    const level = (i % 4) + 1;
    const heading = `${"#".repeat(level)} Sec ${i + 1} **測試** [ref](https://x.test)\n`;
    parts.push(heading);
    const budget = Math.floor(targetBytes / headingCount) - Buffer.byteLength(heading, "utf8");
    let added = 0;
    while (added + fillerBytes <= budget) {
      parts.push(fillerLine);
      added += fillerBytes;
    }
    if (i % 100 === 0) {
      parts.push("```ts\n# not a heading\n```\n");
    }
  }
  return parts.join("");
}

function buildLatexDoc(targetBytes: number, headingCount: number): string {
  const cmds = ["chapter", "section", "subsection", "subsubsection"];
  const parts: string[] = ["\\documentclass{article}\n\\newcommand{\\fake}{\\section{Ignored}}\n\\begin{document}\n"];
  const fillerLine = "學術測試 with \\cite{smith2020} 50\\%.\n";
  const fillerBytes = Buffer.byteLength(fillerLine, "utf8");
  for (let i = 0; i < headingCount; i += 1) {
    const cmd = cmds[i % cmds.length];
    const heading = `\\${cmd}[S${i + 1}]{Full \\textbf{Sec ${i + 1}} 測試}\n`;
    parts.push(heading);
    const budget = Math.floor(targetBytes / headingCount) - Buffer.byteLength(heading, "utf8");
    let added = 0;
    while (added + fillerBytes <= budget) {
      parts.push(fillerLine);
      added += fillerBytes;
    }
    if (i % 100 === 0) {
      parts.push("\\begin{verbatim}\n\\section{Ignored}\n\\end{verbatim}\n");
    }
  }
  parts.push("\\end{document}\n");
  return parts.join("");
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function bench(label: string, path: string, text: string, runs = 20): void {
  // Warm up V8 JIT.
  let count = parseOutline(path, text).flat.length;
  for (let w = 0; w < 3; w += 1) count = parseOutline(path, text).flat.length;

  const times: number[] = [];
  for (let r = 0; r < runs; r += 1) {
    const t0 = performance.now();
    const res = parseOutline(path, text);
    const t1 = performance.now();
    count = res.flat.length;
    times.push(t1 - t0);
  }
  const med = median(times);
  const min = Math.min(...times);
  const max = Math.max(...times);
  const bytes = Buffer.byteLength(text, "utf8");
  console.log(
    `${label}: size=${(bytes / 1024).toFixed(1)} KiB (${bytes} B), headings=${count}, runs=${runs}, median=${med.toFixed(2)} ms, min=${min.toFixed(2)} ms, max=${max.toFixed(2)} ms`,
  );
}

console.log(`Node: ${process.version}`);
console.log(`Platform: ${os.platform()} ${os.release()} (${os.arch()})`);
console.log(`CPU: ${os.cpus()[0]?.model ?? "unknown"} (${os.cpus().length} cores)`);
console.log(`Date: ${new Date().toISOString()}`);
console.log("---");

bench("Markdown ~100 KiB", "bench.md", buildMarkdownDoc(100 * 1024, 1000));
bench("Markdown ~1 MiB  ", "bench.md", buildMarkdownDoc(1024 * 1024, 1000));
bench("LaTeX    ~100 KiB", "bench.tex", buildLatexDoc(100 * 1024, 1000));
bench("LaTeX    ~1 MiB  ", "bench.tex", buildLatexDoc(1024 * 1024, 1000));
