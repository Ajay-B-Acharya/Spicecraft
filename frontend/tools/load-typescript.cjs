'use strict';

// Test-only, in-memory loader, matching frontend/tests/connectivity.test.cjs.
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const cache = new Map();

function load(filename) {
  filename = path.resolve(filename);
  filename = fs.existsSync(filename + '.ts') ? filename + '.ts' : filename;
  if (fs.statSync(filename).isDirectory()) filename = path.join(filename, 'index.ts');
  if (cache.has(filename)) return cache.get(filename).exports;
  const module = { exports: {} };
  cache.set(filename, module);
  try {
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    new Function('require', 'module', 'exports', code)(specifier => {
      if (specifier.startsWith('@/')) return load(path.join(root, specifier.slice(2)));
      if (specifier.startsWith('.')) return load(path.resolve(path.dirname(filename), specifier));
      return require(specifier);
    }, module, module.exports);
    return module.exports;
  } catch (error) {
    cache.delete(filename);
    throw error;
  }
}

module.exports = { load, root };
