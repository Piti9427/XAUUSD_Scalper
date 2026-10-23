// Local contract stand-in: Telegram sendMessage and Healthchecks ping only.
const http = require('http');
http.createServer((req, res) => {
  if (req.url.includes('lost-ack')) {
    req.resume();
    req.on('end', () => req.socket.destroy());
    return;
  }
  if (req.method === 'POST' && req.url.endsWith('/sendMessage')) {
    const body = req.body;
    if (!body || !body.chat_id || !body.text) {
      res.writeHead(400, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({ok: false, error_code: 400, description: 'Bad Request'}));
      return;
    }
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({ok: true, result: {message_id: 1}}));
  } else if (req.method === 'POST' && (req.url === '/ping' || req.url === '/ping/fail')) {
    res.writeHead(200, {'Content-Type': 'text/plain'});
    res.end('OK');
  } else {
    res.writeHead(501);
    res.end('Endpoint not modeled');
  }
}).listen(process.env.PORT);
