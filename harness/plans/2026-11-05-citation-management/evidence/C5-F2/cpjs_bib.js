// Bibliography entries for every item, rendered by citeproc-js.
// Usage: node cpjs_bib.js <style.csl> <items.json> <locale.xml>
const fs = require("fs");
const CSL = require("citeproc");
const [stylePath, itemsPath, localePath] = process.argv.slice(2);
const items = JSON.parse(fs.readFileSync(itemsPath, "utf8"));
const byId = Object.fromEntries(items.map((item) => [item.id, item]));
const engine = new CSL.Engine({ retrieveLocale: () => fs.readFileSync(localePath, "utf8"), retrieveItem: (id) => byId[id] },
  fs.readFileSync(stylePath, "utf8"), "en-US", true);
engine.setOutputFormat("text");
engine.updateItems(items.map((item) => item.id));
const bib = engine.makeBibliography();
process.stdout.write(JSON.stringify(bib[0].entry_ids.map((ids, i) => [ids[0], bib[1][i].trim()])));
