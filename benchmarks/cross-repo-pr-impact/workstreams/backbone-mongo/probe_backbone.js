'use strict';

var path = require('path');
var targetDir = path.resolve(process.argv[2]);
var expectedUrl = 'mongodb://localhost:27017/test';
var connectedUrl = null;
var error = null;

function packageVersion(name) {
  return require(name + '/package.json').version;
}

try {
  var mongodb = require('mongodb');
  mongodb.MongoClient.connect = function(url, options, callback) {
    connectedUrl = url;
    callback(null, {
      close: function() {},
      collection: function(name, done) {
        done(null, { collectionName: name });
      }
    });
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

var passed = !error && connectedUrl === expectedUrl;
console.log(JSON.stringify({
  node: process.version,
  source_backbone: packageVersion('backbone'),
  target_backbone_mongo: require(path.join(targetDir, 'package.json')).version,
  target_backbone_orm: packageVersion('backbone-orm'),
  connected_url: connectedUrl,
  expected_url: expectedUrl,
  error_name: error && error.name,
  error_message: error && error.message,
  result: passed ? 'pass' : 'fail'
}, null, 2));

process.exit(passed ? 0 : 1);
