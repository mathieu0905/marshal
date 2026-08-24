'use strict'

var root = process.cwd()
var karma = require(root + '/node_modules/karma/package.json')
var socket = require(root + '/node_modules/socket.io/package.json')
var engine

try {
  engine = require(root + '/node_modules/socket.io/node_modules/engine.io/package.json')
} catch (error) {
  engine = require(root + '/node_modules/engine.io/package.json')
}

console.log(JSON.stringify({
  node: process.version,
  riot_commit: '18fb94ee2448bcebb0906a7ce813162e76ba13cf',
  riot_version: require(root + '/package.json').version,
  karma_version: karma.version,
  karma_declared_socket_io: karma.dependencies['socket.io'],
  socket_io_version: socket.version,
  engine_io_version: engine.version
}))
