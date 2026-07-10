# AppTrack MCP Server

Claude Code, Cursor ve diğer MCP istemcilerinin AppTrack'e bağlanmasını sağlayan
[Model Context Protocol](https://modelcontextprotocol.io) server'ı. AI ajanları
projelerini listeleyebilir, build tetikleyebilir ve build durumunu sorabilir.

## Araçlar (tools)

| Araç | Açıklama |
|------|----------|
| `list_projects` | Projelerini listeler (id, ad, framework, durum) |
| `get_project` | Bir projenin detayı + runner tipi + son build'ler |
| `trigger_build` | Yeni build başlatır (gerçek CI build — host onayı ister) |
| `get_build_status` | Bir projenin son build'lerini ve durumlarını verir |

`trigger_build` bir **write** işlemidir; MCP host'u (Claude Code/Cursor) çağrı öncesi
kullanıcı onayı gösterir.

## Kurulum

```bash
cd mcp
pip install -r requirements.txt   # mcp[cli]>=1.28,<2 + httpx  (Python 3.10+)
```

## Kimlik doğrulama

1. AppTrack'te **Settings → API Keys → Create key** ile bir anahtar oluştur.
2. Ham anahtarı (`atk_...`) kopyala — yalnızca bir kez gösterilir.

Anahtar **sadece environment variable** ile verilir; asla komut argümanı veya
tool çıktısı olarak gönderilmez. Server anahtarı doğrudan REST'e göndermez; önce
`/api/api-keys/exchange` ile kısa ömürlü access token'a çevirir.

## Claude Code'a ekleme

```bash
claude mcp add --transport stdio apptrack \
  --env APPTRACK_API_KEY=atk_xxx \
  --env APPTRACK_API_URL=http://localhost:8000 \
  -- python -m apptrack_mcp.server
```

Veya `.mcp.json` ile (proje kapsamı):

```json
{
  "mcpServers": {
    "apptrack": {
      "command": "python",
      "args": ["-m", "apptrack_mcp.server"],
      "env": {
        "APPTRACK_API_KEY": "atk_xxx",
        "APPTRACK_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

> `PYTHONPATH`'in `mcp/` dizinini içerdiğinden emin ol veya paketi
> `pip install -e .` ile kurulabilir hale getir. Barındırılan AppTrack için
> `APPTRACK_API_URL`'i kendi gateway adresinle değiştir.

## Örnek kullanım

Claude Code içinde:

> "AppTrack projelerimi listele" → `list_projects`
> "namaz-vakit için iOS build başlat" → `trigger_build(project_id, 'ios')`
> "son build ne durumda?" → `get_build_status(project_id)`

## Güvenlik notları

- Anahtar yalnızca env'de tutulur; loglanmaz, tool argümanı yapılmaz.
- Her anahtar tek bir kullanıcıya bağlıdır; downstream çağrılar o kullanıcının
  yetkisiyle yapılır (confused-deputy'den kaçınılır).
- Anahtarı **Settings → API Keys → Revoke** ile istediğin an iptal edebilirsin.
- Yıkıcı/maliyetli araçlar (`trigger_build`) host onayına tabidir.

## Ortam değişkenleri

| Değişken | Zorunlu | Varsayılan |
|----------|---------|------------|
| `APPTRACK_API_KEY` | evet | — (`atk_` ile başlamalı) |
| `APPTRACK_API_URL` | hayır | `http://localhost:8000` |
| `MCP_TRANSPORT` | hayır | `stdio` (`streamable-http` = HTTP modu) |
| `MCP_PORT` | hayır | `8010` (yalnız HTTP modu) |

## HTTP modu (Faz 2 — kurulumsuz uzak bağlantı)

Docker Compose ile `mcp` servisi Streamable HTTP olarak çalışır (`:8010/mcp`).
stdio'dan farkı: anahtar env'den değil, **istek başına** `Authorization` header'ından
gelir — tek sunucu birden çok kullanıcıya hizmet eder (her anahtar kendi kullanıcısının
yetkisiyle çalışır).

```bash
docker compose up -d mcp        # http://localhost:8010/mcp
curl http://localhost:8010/health
```

Claude Code'a ekleme:

```bash
claude mcp add --transport http apptrack http://localhost:8010/mcp \
  --header "Authorization: Bearer atk_XXXXXXXX"
```

Cursor (`.cursor/mcp.json`):

```json
{ "mcpServers": { "apptrack": {
    "url": "http://localhost:8010/mcp",
    "headers": { "Authorization": "Bearer atk_XXXXXXXX" } } } }
```

Notlar:
- Anahtarsız/geçersiz anahtarlı istekler **401** alır; anahtarlar gateway'in
  `/api/api-keys/exchange` ucuyla doğrulanır (5 dk edge cache).
- OAuth 2.1 resource-server akışı bilinçli olarak sonraya bırakıldı — API-key
  bearer, headless ajanlar için yeterli ve mevcut anahtar altyapısıyla tutarlı.
- Sunucu stateless çalışır; DNS-rebinding koruması kapalıdır çünkü kimlik
  doğrulama zaten Bearer katmanında yapılır ve host adı deploy'a göre değişir.
