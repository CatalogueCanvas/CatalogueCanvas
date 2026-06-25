// Integration step for the per-file coverage runner.
//
// Each test file produces its own report at
//   src/test/.coverage-tmp/<safe-name>/coverage-final.json
// This single process reads every one of those individual reports and merges
// them into one total, then prints line/function/branch/statement percentages.
//
// Standalone: run it on its own against whatever reports exist on disk —
//   node src/test/coverage-merge.mjs [reportsDir]
// (default reportsDir: src/test/.coverage-tmp). It does not run any tests.
//
// Uses istanbul-lib-coverage, which ships with @vitest/coverage-v8 — no install.
import fs from 'node:fs';
import path from 'node:path';
import libCoverage from 'istanbul-lib-coverage';
import libReport from 'istanbul-lib-report';
import reports from 'istanbul-reports';

const tmp = process.argv[2] || 'src/test/.coverage-tmp';
if (!fs.existsSync(tmp)) {
  console.error(`Reports dir not found: ${tmp}`);
  process.exit(1);
}

const map = libCoverage.createCoverageMap({});
let files = 0;
for (const dir of fs.readdirSync(tmp)) {
  const f = path.join(tmp, dir, 'coverage-final.json');
  if (!fs.existsSync(f)) continue;
  map.merge(JSON.parse(fs.readFileSync(f, 'utf8')));
  files++;
}
if (!files) {
  console.error(`No coverage-final.json reports found under ${tmp}`);
  process.exit(1);
}

// Write coverage/lcov.info (what Codacy ingests) from the merged map.
const context = libReport.createContext({ dir: 'coverage', coverageMap: map });
reports.create('lcovonly').execute(context);

const s = map.getCoverageSummary();
const pct = (m) => `${m.pct}% (${m.covered}/${m.total})`;
console.log(`\nMerged ${files} report(s) -> coverage/lcov.info`);
console.log(`  lines:      ${pct(s.lines)}`);
console.log(`  functions:  ${pct(s.functions)}`);
console.log(`  branches:   ${pct(s.branches)}`);
console.log(`  statements: ${pct(s.statements)}`);
