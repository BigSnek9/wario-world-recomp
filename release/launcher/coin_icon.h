// Game icon from the player's own disc: Wario World's gold "W" coin texture.
// C++ twin of installer/coin_icon.py (same steps, same arithmetic, byte-identical .ico; the release
// test checks that). The coin is the 32x32 CMPR texture tex1_32x32_m_5b7df270a43b0ca3_14 in
// files/rsc/ATT.RSC at 0x1148A0 (also AOP.RSC at 0x19E660); its 512 bytes are checked against a
// SHA-256 before use. The generated icon is derived from the player's disc: it is only written into
// the player's own folder and is never shipped.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace coin {

constexpr std::uint32_t kTextureBytes = 512;
constexpr int kTexels = 32;
constexpr double kRadius = 15.6;
constexpr int kSizes[] = {256, 128, 64, 48, 32, 24, 16};
constexpr const char* kSha256 = "7416b9493e5d3349b4741d1ec510312d344761247d517b24ad10e956440201a1";
struct Location {
  const wchar_t* archive;
  std::uint32_t offset;
};
constexpr Location kLocations[] = {{L"files\\rsc\\ATT.RSC", 0x1148A0}, {L"files\\rsc\\AOP.RSC", 0x19E660}};

struct Rgba {
  std::uint8_t r, g, b, a;
};
using Image = std::vector<Rgba>;  // size x size, top-down rows

inline int c5(int v) { return (v << 3) | (v >> 2); }
inline int c6(int v) { return (v << 2) | (v >> 4); }

// Dolphin's generic CMPR decoder rules (8x8 blocks of four DXT1-like 4x4 sub-blocks).
inline std::vector<int> DecodeCmpr(const std::uint8_t* data) {
  std::vector<int> px(kTexels * kTexels * 4, 0);
  std::size_t offset = 0;
  auto be16 = [&](std::size_t o) { return (data[o] << 8) | data[o + 1]; };
  for (int by = 0; by < kTexels; by += 8)
    for (int bx = 0; bx < kTexels; bx += 8)
      for (int sub = 0; sub < 4; ++sub) {
        const int c1 = be16(offset), c2 = be16(offset + 2);
        const std::uint32_t bits = (std::uint32_t(data[offset + 4]) << 24) | (data[offset + 5] << 16) |
                                   (data[offset + 6] << 8) | data[offset + 7];
        offset += 8;
        const int col1[3] = {c5(c1 >> 11 & 31), c6(c1 >> 5 & 63), c5(c1 & 31)};
        const int col2[3] = {c5(c2 >> 11 & 31), c6(c2 >> 5 & 63), c5(c2 & 31)};
        int pal[4][4];
        for (int k = 0; k < 3; ++k) {
          pal[0][k] = col1[k];
          pal[1][k] = col2[k];
          if (c1 > c2) {
            pal[2][k] = (col2[k] * 3 + col1[k] * 5) >> 3;
            pal[3][k] = (col1[k] * 3 + col2[k] * 5) >> 3;
          } else {
            pal[2][k] = pal[3][k] = (col1[k] + col2[k]) / 2;
          }
        }
        pal[0][3] = pal[1][3] = pal[2][3] = 255;
        pal[3][3] = c1 > c2 ? 255 : 0;
        const int sx = bx + (sub & 1) * 4, sy = by + (sub >> 1) * 4;
        for (int y = 0; y < 4; ++y)
          for (int x = 0; x < 4; ++x) {
            const int index = bits >> (30 - 2 * (y * 4 + x)) & 3;
            for (int k = 0; k < 4; ++k) px[((sy + y) * kTexels + sx + x) * 4 + k] = pal[index][k];
          }
      }
  return px;
}

inline void Cubic(double t, double w[4]) {
  const double t2 = t * t, t3 = t * t * t;
  w[0] = -0.5 * t3 + t2 - 0.5 * t;
  w[1] = 1.5 * t3 - 2.5 * t2 + 1.0;
  w[2] = -1.5 * t3 + 2.0 * t2 + 0.5 * t;
  w[3] = 0.5 * t3 - 0.5 * t2;
}

inline void Sample(const std::vector<int>& tex, double u, double v, double out[3]) {
  const double x = u - 0.5, y = v - 0.5;
  const int x0 = int(std::floor(x)), y0 = int(std::floor(y));
  double wx[4], wy[4];
  Cubic(x - x0, wx);
  Cubic(y - y0, wy);
  const int last = kTexels - 1;
  double r = 0.0, g = 0.0, b = 0.0;
  for (int j = 0; j < 4; ++j) {
    const int row = std::min(last, std::max(0, y0 - 1 + j));
    for (int i = 0; i < 4; ++i) {
      const double w = wx[i] * wy[j];
      const int* p = &tex[(row * kTexels + std::min(last, std::max(0, x0 - 1 + i))) * 4];
      r += p[0] * w;
      g += p[1] * w;
      b += p[2] * w;
    }
  }
  out[0] = r;
  out[1] = g;
  out[2] = b;
}

inline std::uint8_t Byte(double v) { return v <= 0.0 ? 0 : v >= 255.0 ? 255 : std::uint8_t(int(v + 0.5)); }

inline Image Render(const std::vector<int>& tex, int size) {
  const double scale = double(kTexels) / size;
  const int samples = std::max(2, int(std::ceil(2.0 * scale)));
  const double centre = kTexels / 2.0;
  Image image(std::size_t(size) * size, Rgba{0, 0, 0, 0});
  for (int oy = 0; oy < size; ++oy)
    for (int ox = 0; ox < size; ++ox) {
      const double dx = (ox + 0.5) * scale - centre, dy = (oy + 0.5) * scale - centre;
      const double distance = std::sqrt(dx * dx + dy * dy) / scale;
      const double coverage = kRadius / scale - distance + 0.5;
      if (coverage <= 0.0) continue;
      double r = 0.0, g = 0.0, b = 0.0;
      for (int sy = 0; sy < samples; ++sy) {
        const double v = (oy + (sy + 0.5) / samples) * scale;
        for (int sx = 0; sx < samples; ++sx) {
          double s[3];
          Sample(tex, (ox + (sx + 0.5) / samples) * scale, v, s);
          r += s[0];
          g += s[1];
          b += s[2];
        }
      }
      const int n = samples * samples;
      image[std::size_t(oy) * size + ox] = Rgba{Byte(r / n), Byte(g / n), Byte(b / n),
                                                Byte(std::min(1.0, coverage) * 255.0)};
    }
  return image;
}

inline void Put16(std::string& s, unsigned v) { s.push_back(char(v & 255)); s.push_back(char(v >> 8 & 255)); }
inline void Put32(std::string& s, std::uint32_t v) { Put16(s, v & 0xFFFF); Put16(s, v >> 16); }

// .ico with uncompressed 32-bit BMP entries plus the AND mask (as coin_icon.ico_bytes).
inline std::string IcoBytes(const std::vector<std::pair<int, Image>>& images) {
  std::vector<std::string> blobs;
  for (const auto& [size, image] : images) {
    const int maskStride = ((size + 31) / 32) * 4;
    std::string pixels, mask;
    for (int y = size - 1; y >= 0; --y) {
      std::string bits(maskStride, '\0');
      for (int x = 0; x < size; ++x) {
        const Rgba& p = image[std::size_t(y) * size + x];
        pixels += char(p.b);
        pixels += char(p.g);
        pixels += char(p.r);
        pixels += char(p.a);
        if (p.a == 0) bits[x >> 3] = char(std::uint8_t(bits[x >> 3]) | (0x80 >> (x & 7)));
      }
      mask += bits;
    }
    std::string blob;
    Put32(blob, 40);
    Put32(blob, size);
    Put32(blob, size * 2);
    Put16(blob, 1);
    Put16(blob, 32);
    Put32(blob, 0);
    Put32(blob, std::uint32_t(pixels.size() + mask.size()));
    for (int i = 0; i < 4; ++i) Put32(blob, 0);
    blobs.push_back(blob + pixels + mask);
  }
  std::string out;
  Put16(out, 0);
  Put16(out, 1);
  Put16(out, unsigned(blobs.size()));
  std::uint32_t offset = 6 + 16 * std::uint32_t(blobs.size());
  std::string entries, data;
  for (std::size_t i = 0; i < blobs.size(); ++i) {
    const int size = images[i].first;
    entries += char(size % 256);
    entries += char(size % 256);
    entries += '\0';
    entries += '\0';
    Put16(entries, 1);
    Put16(entries, 32);
    Put32(entries, std::uint32_t(blobs[i].size()));
    Put32(entries, offset + std::uint32_t(data.size()));
    data += blobs[i];
  }
  return out + entries + data;
}

inline std::string MakeIcon(const std::uint8_t* texture) {
  const std::vector<int> tex = DecodeCmpr(texture);
  std::vector<std::pair<int, Image>> images;
  for (int size : kSizes) images.emplace_back(size, Render(tex, size));
  return IcoBytes(images);
}

}  // namespace coin
