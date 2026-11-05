// Render corpus.json with citeproc-js (reference baseline). Usage:
//   node citeproc_js.js <corpus.json> <styles-dir> <locale.xml> > out.json
const fs = require("fs");
const CSL = require("citeproc");
const [corpusPath, stylesDir, localePath] = process.argv.slice(2);
const corpus = JSON.parse(fs.readFileSync(corpusPath, "utf8"));
const locale = fs.readFileSync(localePath, "utf8");
const styles = ["apa", "modern-language-association", "ieee", "chicago-author-date"];
const out = {};
for (const style of styles) {
  const xml = fs.readFileSync(`${stylesDir}/${style}.csl`, "utf8");
  out[style] = {};
  for (const kase of corpus.cases) {
    const items = Object.fromEntries(kase.items.map((it) => [it.id, it]));
    const sys = { retrieveLocale: () => locale, retrieveItem: (id) => items[id] };
    const engine = new CSL.Engine(sys, xml, "en-US", true);
    engine.setOutputFormat("text");
    const citations = kase.clusters.map((cluster, i) => ({
      citationID: `c${i}`,
      citationItems: cluster.map((x) => ({
        id: x.id,
        ...(x.locator ? { locator: x.locator, label: x.label } : {}),
        ...(x["suppress-author"] ? { "suppress-author": true } : {}),
      })),
      properties: { noteIndex: 0 },
    }));
    const rebuilt = engine.rebuildProcessorState(citations, "text");
    const byId = Object.fromEntries(rebuilt.map(([id, _n, s]) => [id, s]));
    const bib = engine.makeBibliography();
    out[style][kase.id] = {
      citations: citations.map((c) => byId[c.citationID]),
      bibliography: bib ? bib[1].map((e) => e.trim()) : [],
    };
  }
}
process.stdout.write(JSON.stringify(out, null, 1));
