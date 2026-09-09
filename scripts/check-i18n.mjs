/** Guard catalog completeness and unmigrated presentation copy without inspecting user data. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
import { parseTemplate } from '../frontend/node_modules/@angular/compiler/fesm2022/compiler.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const app = path.join(root, 'frontend/src/app');
const failures = [];
function catalog(language) {
  const file = path.join(app, 'i18n', `${language}.ts`);
  const tree = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
  const entries = {};
  function visit(node) {
    if (ts.isPropertyAssignment(node) && ts.isStringLiteral(node.initializer)) {
      const key = node.name.text;
      if (key in entries) failures.push(`Duplicate ${language} key: ${key}`);
      entries[key] = node.initializer.text;
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return entries;
}
const russian = catalog('ru'), english = catalog('en');
const parameters = text => [...new Set(text.match(/\{\w+\}/g) ?? [])].sort().join(',');
for (const key of new Set([...Object.keys(russian), ...Object.keys(english)])) {
  if (!russian[key]?.trim() || !english[key]?.trim()) failures.push(`Missing translation: ${key}`);
  else if (parameters(russian[key]) !== parameters(english[key])) failures.push(`Parameter mismatch: ${key}`);
}
const nativeLabels = new Set(['H', 'Hermes', 'Русский', 'English', 'GET /api/v1/health']);
for (const relative of fs.readdirSync(app, {recursive:true})) {
  if (!/\.(html|ts)$/.test(relative) || relative.endsWith('.spec.ts') || relative.startsWith('i18n/')) continue;
  const content = fs.readFileSync(path.join(app, relative), 'utf8');
  for (const match of content.matchAll(/\bt\('([^']+)'/g)) if (!(match[1] in russian)) failures.push(`${relative}: unknown key ${match[1]}`);
  if (relative.endsWith('.html')) {
    const tree = parseTemplate(content, relative);
    if (tree.errors?.length) failures.push(`${relative}: invalid Angular template`);
    function visit(node) {
      if (node.constructor.name === 'Text' && /[A-Za-zА-Яа-яЁё]/.test(node.value) && !nativeLabels.has(node.value.trim())) failures.push(`${relative}: untranslated text ${node.value.trim()}`);
      if (node.constructor.name === 'TextAttribute' && /^(aria-label|title|placeholder|accessibleLabel|emptyLabel)$/.test(node.name) && /[А-Яа-яЁё]/.test(node.value)) failures.push(`${relative}: untranslated ${node.name}`);
      for (const property of ['children','attributes','inputs','outputs','branches','cases','groups']) for (const child of node[property] ?? []) visit(child);
      if (node.empty) visit(node.empty);
    }
    tree.nodes.forEach(visit);
  } else {
    const tree = ts.createSourceFile(relative, content, ts.ScriptTarget.Latest, true);
    function visit(node) {
      if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && /[А-Яа-яЁё]/.test(node.text)) {
        // Stable, published restore protocol. The visible phrase is translated separately.
        if (!(relative === 'pages/settings/settings.ts' && node.text === 'ЗАМЕНИТЬ ВСЕ ДАННЫЕ')) failures.push(`${relative}: untranslated literal`);
      }
      ts.forEachChild(node, visit);
    }
    visit(tree);
  }
}
if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }
else console.log(`i18n catalogs and source copy: OK (${Object.keys(russian).length} keys per language)`);
