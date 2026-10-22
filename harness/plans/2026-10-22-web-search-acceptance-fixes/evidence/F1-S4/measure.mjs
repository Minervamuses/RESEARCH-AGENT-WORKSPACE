// Doubling measurement for F1-S4: node measure.mjs <dist-dir> <kind: truncate|convert> <KiB>...
// truncate: truncateMarkdown on N KiB of unclosed '[' (limit 10000); convert: parseContent of <pre> with N KiB of spaces.
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const [distArg, kind, ...sizes] = process.argv.slice(2);
const dist = path.resolve(distArg);
const { truncateMarkdown } = await import(pathToFileURL(path.join(dist, 'utils.js')).href);
const { EnhancedContentExtractor } = await import(pathToFileURL(path.join(dist, 'enhanced-content-extractor.js')).href);
const extractor = new EnhancedContentExtractor();
for (const kib of sizes.map(Number)) {
  const begin = performance.now();
  if (kind === 'truncate') truncateMarkdown('['.repeat(kib * 1024) + ' tail', 10000);
  else extractor.parseContent(`<pre>${' '.repeat(kib * 1024)}x</pre>`, 'https://example.org');
  process.stdout.write(JSON.stringify({ kind, kib, ms: Math.round(performance.now() - begin) }) + '\n');
}
