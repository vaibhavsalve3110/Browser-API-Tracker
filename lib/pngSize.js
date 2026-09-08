// Minimal PNG dimension reader (avoids pulling in an image-size dependency).
// PNG spec: bytes 16-19 = width, bytes 20-23 = height, big-endian, in the IHDR chunk.
function getPngSize(buffer) {
  if (buffer.length < 24 || buffer.readUInt32BE(0) !== 0x89504e47) {
    return { width: 800, height: 450 };
  }
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  if (!width || !height) return { width: 800, height: 450 };
  return { width, height };
}

module.exports = { getPngSize };
