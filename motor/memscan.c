/* memscan.c -- SOMENTE LEITURA: procura, na memoria do Evil, objetos cuja primeira palavra e um
 * dado ponteiro de vtable, e despeja seus bytes.
 *   memscan find <pid> <vtable hex>            lista enderecos (regioes rw)
 *   memscan dump <pid> <endereco hex> <bytes>  hexdump (uma linha de hex) */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char** argv)
{
  if (argc < 4) return 2;
  char path[64];
  snprintf(path, sizeof(path), "/proc/%s/mem", argv[2]);
  int fd = open(path, O_RDONLY);
  if (fd < 0) { perror(path); return 1; }
  if (!strcmp(argv[1], "dump"))
  {
    uint32_t addr = (uint32_t)strtoul(argv[3], 0, 16);
    int len = argc > 4 ? atoi(argv[4]) : 256;
    uint8_t* buf = malloc((size_t)len);
    ssize_t n = pread64(fd, buf, (size_t)len, (off64_t)addr);
    if (n <= 0) { perror("pread"); return 1; }
    for (ssize_t i = 0; i < n; i++) printf("%02x", buf[i]);
    printf("\n");
    return 0;
  }
  uint32_t vt = (uint32_t)strtoul(argv[3], 0, 16);
  snprintf(path, sizeof(path), "/proc/%s/maps", argv[2]);
  FILE* maps = fopen(path, "r");
  if (!maps) return 1;
  char line[512];
  static uint8_t buf[1 << 20];
  int hits = 0;
  while (fgets(line, sizeof(line), maps))
  {
    unsigned long a, b; char perm[8];
    if (sscanf(line, "%lx-%lx %7s", &a, &b, perm) != 3) continue;
    if (perm[0] != 'r' || perm[1] != 'w') continue;
    if (strstr(line, "/dev/") || strstr(line, "mali")) continue; /* nao le memoria de dispositivo */
    for (unsigned long p = a; p < b; p += sizeof(buf))
    {
      size_t want = b - p < sizeof(buf) ? b - p : sizeof(buf);
      ssize_t n = pread64(fd, buf, want, (off64_t)p);
      if (n <= 0) break;
      for (ssize_t i = 0; i + 4 <= n; i += 4)
      {
        uint32_t w; memcpy(&w, buf + i, 4);
        if (w == vt) { printf("%lx\n", p + (unsigned long)i); if (++hits >= 64) return 0; }
      }
    }
  }
  return 0;
}
