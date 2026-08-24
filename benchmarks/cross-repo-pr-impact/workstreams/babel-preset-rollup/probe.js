'use strict';

var babel = require('babel-core');
var path = require('path');

var targetDir = path.resolve(process.argv[2]);
var targetPreset = require(targetDir);
var input = 'export default function answer() { return 42; }';
var output = babel.transform(input, { presets: [targetPreset] }).code;
var preservesEsModule = /\bexport\s+default\b/.test(output);
var emitsCommonJs = /\bexports\b|require\s*\(/.test(output);
var passes = preservesEsModule && !emitsCommonJs;

function packageVersion(name) {
  return require(name + '/package.json').version;
}

console.log(JSON.stringify({
  node: process.version,
  babel_core: packageVersion('babel-core'),
  source: packageVersion('babel-preset-es2015'),
  target: require(path.join(targetDir, 'package.json')).version,
  modifier: packageVersion('modify-babel-preset'),
  input: input,
  output: output,
  preserves_es_module: preservesEsModule,
  emits_commonjs: emitsCommonJs,
  result: passes ? 'pass' : 'fail'
}, null, 2));

process.exit(passes ? 0 : 1);
