'use strict';

var http = require('http');
var createRequire = require('module').createRequire;
var requireFromArm = createRequire(process.cwd() + '/probe-entry.js');
var polyclay = requireFromArm('polyclay');
var cradle = requireFromArm('cradle');

var result = {
  adapter: polyclay.CouchAdapter ? 'present' : 'missing',
  callback: false,
  error: null,
  responseJson: null
};

if (!polyclay.CouchAdapter) {
  process.stdout.write(JSON.stringify(result) + '\n');
  process.exit(3);
}

var sockets = [];
var finished = false;
var server = http.createServer(function (request, response) {
  response.statusCode = 200;
  response.end();
});

server.on('connection', function (socket) {
  sockets.push(socket);
});

function finish(error, status) {
  if (finished) return;
  finished = true;
  if (error) result.error = error.name + ': ' + error.message;
  process.stdout.write(JSON.stringify(result) + '\n');
  sockets.forEach(function (socket) { socket.destroy(); });
  server.close(function () { process.exit(status); });
  setTimeout(function () { process.exit(status); }, 250).unref();
}

process.on('uncaughtException', function (error) {
  finish(error, 1);
});

server.listen(0, '127.0.0.1', function () {
  function ProbeModel() {}
  ProbeModel.prototype.plural = 'probe';

  var address = server.address();
  var connection = new cradle.Connection('127.0.0.1', address.port, {
    cache: false,
    retries: 0
  });
  var adapter = new polyclay.CouchAdapter();
  adapter.configure({ connection: connection, dbname: 'probe' }, ProbeModel);

  adapter.remove({ key: 'document', _rev: '1-a' }, function (error, response) {
    result.callback = true;
    if (response && Object.prototype.hasOwnProperty.call(response, 'json')) {
      result.responseJson = response.json;
    }
    finish(error, error ? 1 : 0);
  });
});

setTimeout(function () {
  finish(new Error('调用链在五秒内没有结束'), 2);
}, 5000).unref();
