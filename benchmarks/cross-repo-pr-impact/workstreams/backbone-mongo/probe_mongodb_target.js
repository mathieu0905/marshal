'use strict';

var EventEmitter = require('events').EventEmitter;
var path = require('path');
var targetDir = path.resolve(process.argv[2]);
var fakeDb = new EventEmitter();
var connectedUrl = null;
var error = null;

fakeDb.close = function() {};
fakeDb.collection = function(name, callback) {
  callback(null, { collectionName: name });
};

try {
  var mongodb = require('mongodb');
  mongodb.MongoClient.connect = function(url, options, callback) {
    connectedUrl = url;
    callback(null, fakeDb);
  };
  var Backbone = require('backbone');
  var target = require(targetDir);
  var Model = Backbone.Model.extend({
    urlRoot: 'mongodb://localhost:27017/test/widgets'
  });
  target.sync(Model);
  Model.prototype.sync('sync', new Model(), {});
} catch (caught) {
  error = caught;
}

var passed = !error && connectedUrl === 'mongodb://localhost:27017/test';
console.log(JSON.stringify({
  node: process.version,
  source_mongodb: require('mongodb/package.json').version,
  target_backbone_mongo: require(path.join(targetDir, 'package.json')).version,
  source_backbone: require('backbone/package.json').version,
  connected_url: connectedUrl,
  db_error_listener_count: fakeDb.listeners('error').length,
  error_name: error && error.name,
  error_message: error && error.message,
  result: passed ? 'pass' : 'fail'
}, null, 2));

process.exit(passed ? 0 : 1);
