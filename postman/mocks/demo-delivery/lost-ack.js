// Simulate accepted request with acknowledgement lost before response.
const http = require('http');
http.createServer((req, res) => {
  req.resume();
  req.on('end', () => req.socket.destroy());
}).listen(process.env.PORT);
