'use strict';
// Loaded only by the offline test runner via NODE_OPTIONS.
const net = require('node:net');
net.Socket.prototype.connect = function () {
  throw new Error('Real network connections are disabled in tests');
};
