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
// Uses @vitest/istanbul-lib-coverage and @vitest/istanbul-lib-report, which ship
// with @vitest/coverage-v8 — no install. Vitest 5 forked these from the upstream
// istanbul-* packages and folded the reporter factory (was istanbul-reports) into
// @vitest/istanbul-lib-report, so `create` now comes from there.
import fs from 'node:fs';
import path from 'node:path';
import { createCoverageMap } from '@vitest/istanbul-lib-coverage';
import { create, createContext } from '@vitest/istanbul-lib-report';

// Resolve the reports dir and confirm it stays within the project root, so a
// stray CLI argument can't be used to read files elsewhere (path traversal).
const root = process.cwd();
const tmp = path.resolve(root, process.argv[2] || 'src/test/.coverage-tmp');
if (tmp !== root && !tmp.startsWith(root + path.sep)) {
  console.error(`Reports dir must be inside the project root: ${tmp}`);
  process.exit(1);
}
if (!fs.existsSync(tmp)) {
  console.error(`Reports dir not found: ${tmp}`);
  process.exit(1);
}

const map = createCoverageMap({});
let files = 0;
for (const dir of fs.readdirSync(tmp)) {
  const f = path.join(tmp, dir, 'coverage-final.json');
  if (!fs.existsSync(f)) continue;
  // Skip a malformed/corrupt report rather than aborting the whole merge.
  try {
    map.merge(JSON.parse(fs.readFileSync(f, 'utf8')));
    files++;
  } catch (err) {
    console.warn(`Skipping unreadable coverage report ${f}: ${err.message}`);
  }
}
if (!files) {
  console.error(`No coverage-final.json reports found under ${tmp}`);
  process.exit(1);
}

// Write coverage/lcov.info (what Codacy ingests) from the merged map.
const context = createContext({ dir: 'coverage', coverageMap: map });
create('lcovonly').execute(context);

const s = map.getCoverageSummary();
const pct = (m) => `${m.pct}% (${m.covered}/${m.total})`;
console.log(`\nMerged ${files} report(s) -> coverage/lcov.info`);
console.log(`  lines:      ${pct(s.lines)}`);
console.log(`  functions:  ${pct(s.functions)}`);
console.log(`  branches:   ${pct(s.branches)}`);
console.log(`  statements: ${pct(s.statements)}`);
