const sharp=require('/Users/kimjunghoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const path=require('path');
const base=path.resolve(__dirname,'../../deliverables/v0.2.0/assets');
sharp(path.join(base,'extreme_comparison.svg'),{density:220}).png().toFile(path.join(base,'extreme_comparison.png'));
