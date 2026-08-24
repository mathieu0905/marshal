'use strict';

var EventEmitter = require('events').EventEmitter;
var path = require('path');
var driverDir = path.resolve(process.argv[2]);
var expected = process.argv[3];
var Base = require(path.join(driverDir, 'lib/mongodb/connection/base')).Base;
var base = new Base();
var db = new EventEmitter();
var marker = new Error('probe-callback-error');
var emitted = null;
var propagated = null;

db.databaseName = 'probe';
db.tag = 'probe-tag';
db.openCalled = true;
db.on('error', function(error) {
  emitted = error;
});
base._dbStore._dbs.push(db);

base._registerHandler({
  getRequestId: function() { return 17; }
}, false, {
  socketOptions: { host: 'localhost', port: 27017 }
}, false, function() {
  throw marker;
});

try {
  base._callHandler(17, { ok: 1 }, null);
} catch (error) {
  propagated = error;
}

var observed = emitted === marker ? 'db-error-event' :
  (propagated === marker ? 'callback-throw' : 'other');
var passed = observed === expected;

console.log(JSON.stringify({
  node: process.version,
  mongodb: require(path.join(driverDir, 'package.json')).version,
  expected_behavior: expected,
  observed_behavior: observed,
  db_error_emitted: emitted === marker,
  callback_error_propagated: propagated === marker,
  db_open_called_after: db.openCalled,
  db_store_size_after: base._dbStore._dbs.length,
  result: passed ? 'pass' : 'fail'
}, null, 2));

process.exit(passed ? 0 : 1);
