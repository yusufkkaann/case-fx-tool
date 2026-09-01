# fx-tool

İki para birimi arasında, [Frankfurter](https://frankfurter.dev) (Avrupa Merkez
Bankası referans kurları) üzerinden çevrim yapan küçük bir HTTP servisi. Bir AI
agent tarafından "tool" olarak çağrılacak şekilde tasarlandı; bu yüzden yol
gösteren ilke şu: **yanlış bir sayı, hiç sayı olmamasından beterdir.** Servis asla
bir kur uydurmaz ve bir kuru ait olmadığı bir tarihe aitmiş gibi sunmaz.

## Çalıştırma

```bash
./run.sh        # servisi $PORT üzerinde başlatır (varsayılan 8080)
```

- `FX_UPSTREAM_BASE` — upstream taban URL'i (varsayılan `https://api.frankfurter.dev`)
- `PORT` — dinlenecek port (varsayılan `8080`)

Python 3.11+ gerekir. Script ilk çalıştırmada kendi sanal ortamını (venv) kurar.

## Test

```bash
./test.sh       # testleri hiç ağ kullanmadan çalıştırır
```

Upstream süreç içinde taklit edilir; bu yüzden `FX_UPSTREAM_BASE` kapalı bir porta
işaret etse bile testler geçer.

## Uç nokta (endpoint)

```
GET /tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28
```

`date` opsiyoneldir; verilmezse en son yayınlanan kurlar kullanılır.

### Başarı — `200`

```json
{
  "amount": 250,
  "from": "EUR",
  "to": "TRY",
  "rate": 47.1234,
  "result": 11780.85,
  "rate_date": "2026-08-28",
  "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

- **`rate_date`** kurun gerçekte ait olduğu gündür (upstream cevabından okunur),
  **`asked_date`** ise çağıranın sorduğu gündür.
- ECB, sorulan tarih için bir şey yayınlamadıysa (hafta sonu/tatil), upstream en
  yakın iş gününü döner. Bunu görünür kılarız: `rate_date`, `asked_date`'ten
  farklı olur; böylece model, sayının hangi güne ait olduğunu müşteriye
  söyleyebilir. Tarih sorulmadıysa `asked_date` `null` olur.
- Tutarlar ve kurlar, ikili taban yuvarlama hatalarını önlemek için `float`
  değil `Decimal` ile işlenir. Kur tam hassasiyette tutulur; sonuç 2 ondalığa
  yuvarlanır (`ROUND_HALF_UP`).

### Hata — non-2xx

```json
{ "error": "<machine_code>", "message": "<insanın okuyabileceği bir cümle>" }
```

| HTTP | `error` | Ne zaman |
|---|---|---|
| 400 | `invalid_amount` | `amount` sıfır, negatif veya sonlu değil |
| 400 | `same_currency` | `from` ve `to` aynı |
| 400 | `unknown_currency` | para birimi kodu hatalı ya da ECB tarafından yayınlanmıyor |
| 400 | `future_date` | `date` gelecekte — henüz kur yok |
| 400 | `date_out_of_range` | `date` serinin başlangıcından önce (1999-01-04) |
| 404 | `rate_unavailable` | geçerli girdi için upstream'de kur yok |
| 422 | `invalid_request` | bir sorgu parametresi eksik ya da hatalı |
| 502 | `upstream_unavailable` | upstream'e ulaşılamadı ya da hata döndü |
| 502 | `upstream_invalid_response` | upstream JSON olmayan / bozuk gövde döndü |
| 504 | `upstream_unavailable` | upstream zamanında cevap vermedi |

## Zorunlu durumlarda davranış

| Durum | Davranış |
|---|---|
| Sorulan tarihte kur yok (hafta sonu/tatil) | En son yayınlanan kuru döner; `rate_date` gerçek günü gösterir. |
| Tarih gelecekte | `400 future_date` — upstream'e gitmeden doğrulanır. |
| Tarih seri başlangıcından önce | `400 date_out_of_range`. |
| Para birimi yok | `400 unknown_currency` (upstream para birimi listesine karşı doğrulanır). |
| `from == to` | `400 same_currency`. |
| Upstream yavaş / 500 / JSON değil | `504` / `502 upstream_unavailable` / `502 upstream_invalid_response` — asla uydurma sayı. |
| `amount` eksik / sıfır / negatif | `422 invalid_request` / `400 invalid_amount`. Yüksek hassasiyetli tutarlar kabul edilir; sonuç 2 ondalığa yuvarlanır. |

## Önbellek (cache)

Aynı istekler süreç içi bir önbellekten karşılanır; upstream'e tekrar sorulmaz.
Sabit bir geçmiş tarihe ait kur süresiz cache'lenir (hiç değişmez); "latest" kuru
kısa bir TTL ile cache'lenir. Yayınlanan para birimi listesi de cache'lenir.

## Tasarım notları

Bkz. [`NOTES.md`](./NOTES.md). Part B kod incelemesi [`REVIEW.md`](./REVIEW.md)
içinde.

## Dizin yapısı

```
app/
  config.py     ortam değişkenlerinden ayarlar
  errors.py     hata kodları ve alan (domain) hata tipi
  models.py     cevap modeli
  cache.py      küçük TTL önbellek
  upstream.py   Frankfurter istemcisi (timeout, durum kontrolü, gerçek tarihi okur)
  service.py    doğrulama, fallback politikası, önbellek, hesaplama
  main.py       FastAPI uygulaması, uç nokta, hata handler'ları
tests/          sahte upstream ile ağsız testler
```
