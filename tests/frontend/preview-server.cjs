// Local multipart fixture for actual browser image decoding and connection lifecycle.
const http = require("node:http");
const frames = [
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAkAEADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAb/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwCnQYAAAAAAAAAAAAAAAAAAAAAD//2Q==",
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAkAEADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAL/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAb/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCgE+uQAAAAAAAAAAAAAAAAAAAAAH//2Q==",
].map((data) => Buffer.from(data, "base64"));
async function startPreviewServer() {
  const responses = new Set();
  const stats = { active: 0, connections: 0, frames: 0 };
  const server = http.createServer((request, response) => {
    if (request.url === "/service-worker.js") {
      response.writeHead(200, {
        "Content-Type": "application/javascript",
        "Cache-Control": "no-store",
      });
      response.end(`
        self.addEventListener("install", () => self.skipWaiting());
        self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
        self.addEventListener("fetch", event => {
          if (new URL(event.request.url).pathname.startsWith("/api/"))
            event.respondWith(fetch(event.request));
        });
      `);
      return;
    }
    if (!request.url.startsWith("/api/camera_proxy_stream/")) {
      response.end(
        '<body style="margin:16px;background:#f4f5f8;font-family:Arial;color:#172b3a"></body>',
      );
      return;
    }
    responses.add(response);
    stats.active++;
    stats.connections++;
    response.writeHead(200, {
      "Content-Type": request.url.includes("lg_preview=frames")
        ? "application/octet-stream"
        : "multipart/x-mixed-replace; boundary=lg-display-frame",
      "Cache-Control": "no-store",
    });
    const send = () => {
      const frame = frames[Math.floor(stats.frames++ / 3) % frames.length];
      response.write(
        `--lg-display-frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${frame.length}\r\n\r\n`,
      );
      response.write(frame);
      response.write("\r\n");
    };
    send();
    send();
    const timer = setInterval(send, 150);
    response.on("close", () => {
      responses.delete(response);
      clearInterval(timer);
      stats.active--;
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    url: `http://127.0.0.1:${server.address().port}`,
    stats,
    disconnect: () => responses.forEach((response) => response.end()),
    close: () =>
      new Promise((resolve) => {
        server.close(resolve);
        server.closeAllConnections();
      }),
  };
}
module.exports = { startPreviewServer };
