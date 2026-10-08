'use strict';

// Observe real compiler inputs in the existing tests; never emit or edit TS.
const fs = require('node:fs');
const Module = require('node:module');
const originalLoad = Module._load;
const output = process.env.CIRCUIT_CORPUS_CAPTURE;
const source = process.env.CIRCUIT_CORPUS_SOURCE;
const seen = new Set();
globalThis.__corpusCapture = input => {
  const frames = new Error().stack.split('\n').filter(line => line.includes(source));
  const locations = frames.map(line => line.match(/:(\d+):(\d+)\)?$/)).filter(Boolean);
  const line = locations.length ? Number(locations[locations.length - 1][1]) : 1;
  try {
    const inspect = (value, ancestors = new Set()) => {
      if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Non-finite input cannot be represented losslessly as JSON.');
      if (['undefined', 'function', 'symbol', 'bigint'].includes(typeof value)) throw new Error(`Non-JSON ${typeof value} input retained as unresolved evidence.`);
      if (value === null || typeof value !== 'object') return;
      if (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw new Error('Non-JSON object prototype retained as unresolved evidence.');
      if (ancestors.has(value)) throw new Error('Cyclic input cannot be snapshotted as JSON.');
      ancestors.add(value);
      for (const descriptor of Object.values(Object.getOwnPropertyDescriptors(value))) {
        if (descriptor.get || descriptor.set) throw new Error('Accessor input retained as unresolved evidence; accessors are not evaluated by collection.');
        inspect(descriptor.value, ancestors);
      }
      ancestors.delete(value);
    };
    inspect(input);
    const serialized = JSON.stringify(input);
    const key = `${line}:${serialized}`;
    if (serialized === undefined || seen.has(key)) return;
    seen.add(key);
    fs.appendFileSync(output, JSON.stringify({ input: JSON.parse(serialized), line }) + '\n');
  } catch (error) {
    fs.appendFileSync(output, JSON.stringify({ error: error.message, line }) + '\n');
  }
};
Module._load = function (id, parent, main) {
  const loaded = originalLoad.call(this, id, parent, main);
  if (id !== 'typescript') return loaded;
  // A plain facade avoids Proxy invariants on TypeScript's getter exports.
  return { ...loaded, transpileModule(text, options) {
    const result = loaded.transpileModule(text, options);
    if (/export class CircuitCompiler\b/.test(text)) {
      result.outputText += '\nconst __originalCompile = CircuitCompiler.compile;\n' +
        'CircuitCompiler.compile = function(input) { globalThis.__corpusCapture(input); return __originalCompile.call(this, input); };\n';
    }
    return result;
  } };
};

function staticDefinitions(filename, text) {
  const path = require('node:path');
  const ts = require(path.resolve(__dirname, '../../../frontend/node_modules/typescript'));
  const tree = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true);
  const found = [], unresolved = [];
  const helpers = new Map();
  function evaluate(node, env, depth = 0) {
    if (!node || depth > 20) throw new Error('Dynamic/missing expression');
    const ev = item => evaluate(item, env, depth + 1);
    if (ts.isStringLiteralLike(node) || ts.isNumericLiteral(node)) return ts.isNumericLiteral(node) ? Number(node.text) : node.text;
    if (node.kind === ts.SyntaxKind.NullKeyword) return null;
    if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
    if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
    if (ts.isIdentifier(node)) {
      if (!env.has(node.text)) throw new Error(`Dynamic name: ${node.text}`);
      return env.get(node.text);
    }
    if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)) return ev(node.expression);
    if (ts.isConditionalExpression(node)) return ev(ev(node.condition) ? node.whenTrue : node.whenFalse);
    if (ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken].includes(node.operatorToken.kind)) return ev(node.left) === ev(node.right);
    if (ts.isArrayLiteralExpression(node)) return node.elements.flatMap(item => ts.isSpreadElement(item) ? ev(item.expression) : [ev(item)]);
    if (ts.isObjectLiteralExpression(node)) {
      const value = Object.create(null);
      for (const property of node.properties) {
        if (ts.isSpreadAssignment(property)) Object.assign(value, ev(property.expression));
        else if (ts.isShorthandPropertyAssignment(property)) value[property.name.text] = ev(property.name);
        else if (ts.isPropertyAssignment(property)) value[property.name.text] = ev(property.initializer);
        else throw new Error('Dynamic object property');
      }
      return value;
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && helpers.has(node.expression.text)) {
      const helper = helpers.get(node.expression.text), local = new Map(env);
      helper.parameters.forEach((parameter, index) => local.set(parameter.name.text,
        index < node.arguments.length ? ev(node.arguments[index]) : parameter.initializer ? evaluate(parameter.initializer, local, depth + 1) : undefined));
      return evaluate(helper.body, local, depth + 1);
    }
    throw new Error(`Dynamic expression: ${node.getText(tree).slice(0, 100)}`);
  }
  function record(node, env) {
    const object = ts.isObjectLiteralExpression(node) && node.properties.some(property => ['components', 'nodes'].includes(property.name?.text));
    const call = ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'circuit' && helpers.has('circuit');
    if (!object && !call) return;
    const line = tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1;
    try {
      const input = evaluate(node, env);
      JSON.stringify(input, (_key, value) => {
        if (value === undefined || typeof value === 'number' && !Number.isFinite(value)) throw new Error('Expression is not losslessly representable as JSON.');
        return value;
      });
      if (input && typeof input === 'object' && ('components' in input || 'nodes' in input)) {
        const components = input.components ?? input.nodes;
        if (!filename.includes('/tests/') && (!Array.isArray(components) || components.length === 0)) return;
        if (Array.isArray(components) && components.some(item => typeof item === 'string')) return;
        found.push({ line, input });
      }
    } catch (error) {
      unresolved.push({ line, expression: node.getText(tree), reason: error.message });
    }
  }
  function bind(name, value, env) {
    if (ts.isIdentifier(name)) env.set(name.text, value);
    else if (ts.isArrayBindingPattern(name)) name.elements.forEach((item, index) => bind(item.name, value[index], env));
  }
  function walk(node, env) {
    if (ts.isVariableDeclaration(node) && node.initializer) {
      if (ts.isArrowFunction(node.initializer) && ['component', 'circuit'].includes(node.name.text)) {
        helpers.set(node.name.text, node.initializer);
        return;
      }
      try { bind(node.name, evaluate(node.initializer, env), env); } catch {}
    }
    if (ts.isForOfStatement(node)) {
      try {
        const values = evaluate(node.expression, env);
        if (values.length > 1000) throw new Error('Loop limit');
        for (const value of values) {
          const local = new Map(env);
          bind(node.initializer.declarations[0].name, value, local);
          walk(node.statement, local);
        }
        return;
      } catch {}
    }
    record(node, env);
    if (ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node)) {
      ts.forEachChild(node, child => walk(child, new Map(env)));
    } else ts.forEachChild(node, child => walk(child, env));
  }
  walk(tree, new Map());
  return { source: filename, found, unresolved };
}

if (require.main === module && process.argv.includes('--static')) {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify(request.map(item => staticDefinitions(item.source, item.text))) + '\n');
}
